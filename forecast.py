import pandas as pd
import numpy as np
from db_utils import get_net_sales_data, get_all_skus
from cache_service import get_cached_forecasts, save_forecast_cache
from forecast_schema import INTERNAL_FORECAST_COLUMNS

FORECAST_COLUMNS = INTERNAL_FORECAST_COLUMNS


def _optimize_forecast_dtypes(df):
    if df.empty:
        return df

    float_cols = ['whole_period_sales', 'sales_interval_m4w', 'sales_interval_m3w', 'sales_interval_m2w', 'sales_interval_m1w', 'trend_coef']
    int_cols = ['forecast_interval_p1w', 'forecast_interval_p2w', 'forecast_interval_p3w', 'forecast_interval_p4w', 'whole_period_forecast']

    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype('float32')
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype('int32')
    return df


def _empty_forecast_row(sku):
    return {
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
    }


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
    
    # Intervals must be passed in chronological order.
    if start_date > end_date:
        raise ValueError(
            f"Invalid interval bounds: start_day={start_day}, end_day={end_day}"
        )
    
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


def calculate_trend_and_forecast(trend_period_weeks=8):
    """
    trend_period_weeks: сколько недель истории использовать для прогноза
    
    All sales and forecast calculations use the same reference date: latest date from loaded log files.
    """

    raw_df = get_net_sales_data()

    if raw_df.empty:
        # Get all SKUs and create forecasts with 0
        all_skus = get_all_skus()
        _empty_cols = FORECAST_COLUMNS.copy()
        if not all_skus:
            result = pd.DataFrame(columns=_empty_cols)
            save_forecast_cache(result, trend_period_weeks=trend_period_weeks)
            return result
        forecasts = [_empty_forecast_row(sku) for sku in all_skus]
        result = pd.DataFrame(forecasts)
        result = _optimize_forecast_dtypes(result)
        save_forecast_cache(result, trend_period_weeks=trend_period_weeks)
        return result

    raw_df['date'] = pd.to_datetime(raw_df['date'])
    raw_df = raw_df.sort_values(['sku', 'date'])
    global_latest_date = raw_df['date'].max()

    weekly_df = raw_df[['sku', 'date', 'outbound']].copy()
    weekly_df['week'] = weekly_df['date'].dt.to_period('W').apply(lambda r: r.start_time)
    weekly_df = (
        weekly_df.groupby(['sku', 'week'], as_index=False)['outbound']
        .sum()
        .sort_values(['sku', 'week'])
    )

    daily_df = (
        raw_df.groupby(['sku', 'date'], as_index=False)['outbound']
        .sum()
        .sort_values(['sku', 'date'])
    )

    weekly_series_by_sku = {
        sku: group['outbound'].reset_index(drop=True)
        for sku, group in weekly_df.groupby('sku')
    }
    daily_series_by_sku = {
        sku: group.set_index('date')['outbound']
        for sku, group in daily_df.groupby('sku')
    }

    forecasts = []
    trend_weeks = max(2, int(trend_period_weeks))
    whole_period_days = max(1, int(7 * trend_weeks))
    all_skus = get_all_skus()

    def _sum_interval(series, start_day, end_day):
        start_date = global_latest_date + pd.Timedelta(days=start_day)
        end_date = global_latest_date + pd.Timedelta(days=end_day)
        if start_date > end_date:
            raise ValueError(
                f"Invalid interval bounds: start_day={start_day}, end_day={end_day}"
            )
        return float(series.loc[(series.index >= start_date) & (series.index <= end_date)].sum())

    
    for sku in all_skus:
        weekly_series = weekly_series_by_sku.get(sku)
        daily_series = daily_series_by_sku.get(sku)

        if weekly_series is None or weekly_series.empty or daily_series is None or daily_series.empty:
            forecasts.append(_empty_forecast_row(sku))
            continue

        recent = weekly_series.tail(trend_weeks)

        if recent.empty:
            forecasts.append(_empty_forecast_row(sku))
            continue
        else:
            trend, forecast_interval_p1w, forecast_interval_p2w, forecast_interval_p3w, forecast_interval_p4w = _linear_weekly_forecast(recent)

            # All calculations use the same reference date from latest log file.
            sales_interval_m4w = _sum_interval(daily_series, -27, -21)
            sales_interval_m3w = _sum_interval(daily_series, -20, -14)
            sales_interval_m2w = _sum_interval(daily_series, -13, -7)
            sales_interval_m1w = _sum_interval(daily_series, -6, 0)
            # whole_period_sales uses trend_weeks * 7 days ending at the global reference date.
            whole_period_sales = _sum_interval(daily_series, -(whole_period_days - 1), 0)

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
        save_forecast_cache(result, trend_period_weeks=trend_period_weeks)
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
    result = _optimize_forecast_dtypes(result)

    # Save to cache
    save_forecast_cache(result, trend_period_weeks=trend_period_weeks)

    return result


def get_forecasts(trend_period_weeks=8):
    """
    Возвращает прогнозы из кэша или рассчитывает новые
    """
    cached = get_cached_forecasts(trend_period_weeks=trend_period_weeks)
    if not cached.empty and 'sku' in cached.columns:
        ordered_cols = [c for c in FORECAST_COLUMNS if c in cached.columns]
        if 'last_updated' in cached.columns:
            ordered_cols.append('last_updated')
        return cached.reindex(columns=ordered_cols)

    return calculate_trend_and_forecast(trend_period_weeks=trend_period_weeks)
