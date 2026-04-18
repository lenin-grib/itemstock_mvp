import pandas as pd
import numpy as np
from db_utils import get_net_sales_data, get_all_skus
from cache_service import get_cached_forecasts, save_forecast_cache, invalidate_forecast_cache
from forecast_schema import INTERNAL_FORECAST_COLUMNS


FORECAST_COLUMNS = INTERNAL_FORECAST_COLUMNS


def get_last_n_days_sales(raw_df, sku, n_days, reference_date=None):
    sku_df = raw_df[raw_df['sku'] == sku].sort_values('date')
    if sku_df.empty:
        return 0

    latest_date = reference_date if reference_date is not None else sku_df['date'].max()
    cutoff_date = latest_date - pd.Timedelta(days=n_days - 1)
    return sku_df.loc[sku_df['date'] >= cutoff_date, 'outbound'].sum()


def get_sales_interval(raw_df, sku, start_day, end_day, reference_date=None):
    """
    Get sales for a specific day interval relative to reference_date.
    start_day and end_day are negative (past) or positive (future) offsets from reference_date.
    For example: start_day=-7, end_day=-1 gets sales from 7 days ago to yesterday.
    """
    sku_df = raw_df[raw_df['sku'] == sku].sort_values('date')
    if sku_df.empty:
        return 0

    latest_date = reference_date if reference_date is not None else sku_df['date'].max()
    
    # Convert day offsets to dates
    # For past intervals (negative offsets): -7 means 7 days before reference
    # For future intervals (positive offsets): +1 means 1 day after reference
    start_date = latest_date + pd.Timedelta(days=start_day)
    end_date = latest_date + pd.Timedelta(days=end_day)
    
    # Ensure proper ordering
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    
    return sku_df.loc[(sku_df['date'] >= start_date) & (sku_df['date'] <= end_date), 'outbound'].sum()


def _linear_weekly_forecast(recent_series):
    """
    Линейный прогноз по последним N неделям.
    Возвращает (trend_coef, forecast_interval_1w, forecast_interval_2w, forecast_interval_3w, forecast_interval_4w).
    Each forecast_interval represents the forecast for that individual week only.
    """
    values = recent_series.to_numpy(dtype=float)
    if len(values) == 0:
        return 1.0, 0.0, 0.0, 0.0, 0.0

    avg_weekly = float(np.mean(values))
    if len(values) < 2:
        # For small samples, return equal distribution across weeks
        weekly_avg = max(0.0, avg_weekly)
        return (
            1.0,
            weekly_avg,
            weekly_avg,
            weekly_avg,
            weekly_avg,
        )

    x = np.arange(len(values), dtype=float)
    slope, intercept = np.polyfit(x, values, 1)

    next_week_raw = intercept + slope * len(values)
    if avg_weekly <= 0:
        trend = 1.0
    else:
        trend = next_week_raw / avg_weekly
    trend = float(np.clip(trend, 0.5, 1.5))

    # Calculate forecast for each individual week
    future_x = np.arange(len(values), len(values) + 4, dtype=float)
    future_vals = intercept + slope * future_x
    future_vals = np.clip(future_vals, a_min=0.0, a_max=None)

    # Each forecast_interval is just the value for that week
    forecast_interval_1w = float(future_vals[0])
    forecast_interval_2w = float(future_vals[1])
    forecast_interval_3w = float(future_vals[2])
    forecast_interval_4w = float(future_vals[3])

    return trend, forecast_interval_1w, forecast_interval_2w, forecast_interval_3w, forecast_interval_4w


def calculate_sales_metrics():
    """
    Загружает данные из БД и рассчитывает метрики

    Возвращает:
    DataFrame с метриками по каждому SKU
    """

    df = get_net_sales_data()
    all_skus = get_all_skus()

    if df.empty:
        # Return empty metrics for all SKUs
        return pd.DataFrame({
            'sku': all_skus,
            'total_sales': 0,
            'avg_weekly_sales': 0,
            'avg_monthly_sales': 0
        }), pd.DataFrame()

    # Ensure date is datetime
    df['date'] = pd.to_datetime(df['date'])

    # агрегируем по неделям
    df["week"] = df["date"].dt.to_period("W").apply(lambda r: r.start_time)

    weekly = df.groupby(["sku", "week"], as_index=False)["outbound"].sum()

    # total sales
    total_sales = weekly.groupby("sku")["outbound"].sum().reset_index(name="total_sales")

    # средние
    weekly_stats = weekly.groupby("sku")["outbound"].agg(
        avg_weekly_sales="mean"
    ).reset_index()

    monthly_stats = weekly.groupby("sku")["outbound"].agg(
        avg_monthly_sales=lambda x: x.mean() * 4
    ).reset_index()

    result = total_sales.merge(weekly_stats, on="sku").merge(monthly_stats, on="sku")

    # Add SKUs with no sales
    existing_skus = set(result['sku'])
    missing_skus = [sku for sku in all_skus if sku not in existing_skus]
    if missing_skus:
        missing_df = pd.DataFrame({
            'sku': missing_skus,
            'total_sales': 0,
            'avg_weekly_sales': 0,
            'avg_monthly_sales': 0
        })
        result = pd.concat([result, missing_df], ignore_index=True)

    return result, weekly


def calculate_trend_and_forecast(weekly_df=None, trend_period_weeks=8):
    """
    weekly_df: sku, week, outbound (если None, загружает из БД)
    trend_period_weeks: сколько недель истории использовать для прогноза
    
    All sales and forecast calculations use the same reference date: latest date from loaded log files.
    """

    raw_df = None
    global_latest_date = None
    
    # Always load raw_df to establish consistent reference date from actual log files
    if weekly_df is None:
        raw_df = get_net_sales_data()

        if raw_df.empty:
            # Get all SKUs and create forecasts with 0
            all_skus = get_all_skus()
            _empty_cols = FORECAST_COLUMNS.copy()
            if not all_skus:
                result = pd.DataFrame(columns=_empty_cols)
                save_forecast_cache(result)
                return result
            forecasts = []
            for sku in all_skus:
                forecasts.append({
                    "sku": sku,
                    "sales_interval_m4w": 0,
                    "sales_interval_m3w": 0,
                    "sales_interval_m2w": 0,
                    "sales_interval_m1w": 0,
                    "whole_period_sales": 0,
                    "trend_coef": 1,
                    "forecast_interval_p1w": 0,
                    "forecast_interval_p2w": 0,
                    "forecast_interval_p3w": 0,
                    "forecast_interval_p4w": 0,
                    "whole_period_forecast": 0,
                })
            result = pd.DataFrame(forecasts)
            save_forecast_cache(result)
            return result

        raw_df['date'] = pd.to_datetime(raw_df['date'])
        raw_df = raw_df.sort_values(['sku', 'date'])
        global_latest_date = raw_df['date'].max()
        weekly_df = raw_df.copy()
        weekly_df['week'] = weekly_df['date'].dt.to_period('W').apply(lambda r: r.start_time)
        weekly_df = weekly_df.groupby(['sku', 'week'], as_index=False)['outbound'].sum()
    else:
        # If weekly_df is provided, we still need to load raw_df to get consistent reference date
        # and to calculate individual day intervals
        raw_df = get_net_sales_data()
        if not raw_df.empty:
            raw_df['date'] = pd.to_datetime(raw_df['date'])
            raw_df = raw_df.sort_values(['sku', 'date'])
            global_latest_date = raw_df['date'].max()
        else:
            # If no raw data available, extract max date from weekly_df
            if 'week' in weekly_df.columns:
                global_latest_date = pd.to_datetime(weekly_df['week'].max())

    weekly_df = weekly_df.sort_values(['sku', 'week'])

    forecasts = []
    trend_weeks = max(2, int(trend_period_weeks))
    whole_period_days = max(1, int(7 * trend_weeks))
    all_skus = get_all_skus()
    
    # Log reference date for consistency check
    # All sales_interval_* and whole_period_sales calculations use this reference date
    if global_latest_date is not None:
        reference_date_str = global_latest_date.strftime('%Y-%m-%d')
    else:
        reference_date_str = "None (using SKU-specific max dates)"

    for sku in all_skus:
        group = weekly_df[weekly_df['sku'] == sku].sort_values('week')
        recent = group.tail(trend_weeks)

        if recent.empty:
            # No sales data - return zeros with all interval columns
            sales_interval_m4w = 0
            sales_interval_m3w = 0
            sales_interval_m2w = 0
            sales_interval_m1w = 0
            whole_period_sales = 0
            trend = 1
            forecast_interval_p1w = 0
            forecast_interval_p2w = 0
            forecast_interval_p3w = 0
            forecast_interval_p4w = 0
            whole_period_forecast = 0
        else:
            trend, forecast_interval_p1w, forecast_interval_p2w, forecast_interval_p3w, forecast_interval_p4w = _linear_weekly_forecast(recent['outbound'])

            if raw_df is not None and global_latest_date is not None:
                # All calculations use the same reference date from latest log file
                # Calculate individual week intervals for display (each 7 days, non-overlapping)
                # m4w: days -27 to -21 (7 days)
                # m3w: days -20 to -14 (7 days)
                # m2w: days -13 to -7 (7 days)
                # m1w: days -6 to 0 (7 days)
                # Total: 28 days
                sales_interval_m4w = get_sales_interval(raw_df, sku, -27, -21, reference_date=global_latest_date)
                sales_interval_m3w = get_sales_interval(raw_df, sku, -20, -14, reference_date=global_latest_date)
                sales_interval_m2w = get_sales_interval(raw_df, sku, -13, -7, reference_date=global_latest_date)
                sales_interval_m1w = get_sales_interval(raw_df, sku, -6, 0, reference_date=global_latest_date)
                # whole_period_sales = all sales from (reference_date - trend_weeks*4 days) to reference_date
                # This covers the full lookback period, which may be more than 28 days
                whole_period_sales = get_last_n_days_sales(
                    raw_df,
                    sku,
                    whole_period_days,
                    reference_date=global_latest_date,
                )
            else:
                # Fallback to weekly data when raw daily data not available
                # Use the last date in weekly_df as reference
                if not group.empty:
                    fallback_ref_date = group.iloc[-1]['week']
                else:
                    fallback_ref_date = global_latest_date
                    
                sales_interval_m1w = group.iloc[-1]['outbound'] if not group.empty else 0
                sales_interval_m2w = group.iloc[-2]['outbound'] if len(group) >= 2 else 0
                sales_interval_m3w = group.iloc[-3]['outbound'] if len(group) >= 3 else 0
                sales_interval_m4w = group.iloc[-4]['outbound'] if len(group) >= 4 else 0
                # whole_period_sales = sum of last trend_weeks weeks (consistent with trend lookback)
                whole_period_sales = group.tail(trend_weeks)['outbound'].sum()

            # Calculate total forecast
            whole_period_forecast = forecast_interval_p1w + forecast_interval_p2w + forecast_interval_p3w + forecast_interval_p4w

        forecasts.append({
            "sku": sku,
            "sales_interval_m4w": sales_interval_m4w,
            "sales_interval_m3w": sales_interval_m3w,
            "sales_interval_m2w": sales_interval_m2w,
            "sales_interval_m1w": sales_interval_m1w,
            "whole_period_sales": whole_period_sales,
            "trend_coef": trend,
            "forecast_interval_p1w": forecast_interval_p1w,
            "forecast_interval_p2w": forecast_interval_p2w,
            "forecast_interval_p3w": forecast_interval_p3w,
            "forecast_interval_p4w": forecast_interval_p4w,
            "whole_period_forecast": whole_period_forecast,
        })

    _result_cols = FORECAST_COLUMNS.copy()
    if not forecasts:
        result = pd.DataFrame(columns=_result_cols)
        save_forecast_cache(result)
        return result
    result = pd.DataFrame(forecasts)
    result = result.assign(
        forecast_interval_p1w=lambda df: np.ceil(df["forecast_interval_p1w"]).astype(int),
        forecast_interval_p2w=lambda df: np.ceil(df["forecast_interval_p2w"]).astype(int),
        forecast_interval_p3w=lambda df: np.ceil(df["forecast_interval_p3w"]).astype(int),
        forecast_interval_p4w=lambda df: np.ceil(df["forecast_interval_p4w"]).astype(int),
        whole_period_forecast=lambda df: np.ceil(df["whole_period_forecast"]).astype(int),
    )[FORECAST_COLUMNS]

    # Ensure unique SKU
    result = result.drop_duplicates(subset='sku')

    # Save to cache
    save_forecast_cache(result)

    return result


def get_forecasts(trend_period_weeks=8):
    """
    Возвращает прогнозы из кэша или рассчитывает новые
    """
    cached = get_cached_forecasts()
    if not cached.empty and 'sku' in cached.columns:
        ordered_cols = [c for c in FORECAST_COLUMNS if c in cached.columns]
        if 'last_updated' in cached.columns:
            ordered_cols.append('last_updated')
        return cached.reindex(columns=ordered_cols)

    return calculate_trend_and_forecast(trend_period_weeks=trend_period_weeks)
