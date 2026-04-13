import pandas as pd
import numpy as np
from db_utils import get_sales_data, get_all_skus
from cache_service import get_cached_forecasts, save_forecast_cache, invalidate_forecast_cache


def get_last_n_days_sales(raw_df, sku, n_days, reference_date=None):
    sku_df = raw_df[raw_df['sku'] == sku].sort_values('date')
    if sku_df.empty:
        return 0

    latest_date = reference_date if reference_date is not None else sku_df['date'].max()
    cutoff_date = latest_date - pd.Timedelta(days=n_days - 1)
    return sku_df.loc[sku_df['date'] >= cutoff_date, 'outbound'].sum()


def _linear_weekly_forecast(recent_series):
    """
    Линейный прогноз по последним N неделям.
    Возвращает (trend_coef, forecast_next_week, forecast_next_month).
    """
    values = recent_series.to_numpy(dtype=float)
    if len(values) == 0:
        return 1.0, 0.0, 0.0

    avg_weekly = float(np.mean(values))
    if len(values) < 2:
        return 1.0, max(0.0, avg_weekly), max(0.0, avg_weekly * 4)

    x = np.arange(len(values), dtype=float)
    slope, intercept = np.polyfit(x, values, 1)

    next_week_raw = intercept + slope * len(values)
    if avg_weekly <= 0:
        trend = 1.0
    else:
        trend = next_week_raw / avg_weekly
    trend = float(np.clip(trend, 0.5, 1.5))

    forecast_1w = max(0.0, avg_weekly * trend)

    future_x = np.arange(len(values), len(values) + 4, dtype=float)
    future_vals = intercept + slope * future_x
    future_vals = np.clip(future_vals, a_min=0.0, a_max=None)
    forecast_4w = float(np.sum(future_vals))

    return trend, forecast_1w, forecast_4w


def calculate_sales_metrics():
    """
    Загружает данные из БД и рассчитывает метрики

    Возвращает:
    DataFrame с метриками по каждому SKU
    """

    df = get_sales_data()
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
    """

    raw_df = None
    global_latest_date = None
    if weekly_df is None:
        raw_df = get_sales_data()

        if raw_df.empty:
            # Get all SKUs and create forecasts with 0
            from db_utils import get_all_skus
            all_skus = get_all_skus()
            forecasts = []
            for sku in all_skus:
                forecasts.append({
                    "sku": sku,
                    "sales_last_week": 0,
                    "sales_last_month": 0,
                    "whole_period_sales": 0,
                    "trend_coef": 1,
                    "forecast_next_week": 0,
                    "forecast_next_month": 0,
                })
            result = pd.DataFrame(forecasts)
            save_forecast_cache(result)
            return result

        raw_df['date'] = pd.to_datetime(raw_df['date'])
        global_latest_date = raw_df['date'].max()
        weekly_df = raw_df.copy()
        weekly_df['week'] = weekly_df['date'].dt.to_period('W').apply(lambda r: r.start_time)
        weekly_df = weekly_df.groupby(['sku', 'week'], as_index=False)['outbound'].sum()

    weekly_df = weekly_df.sort_values(['sku', 'week'])

    forecasts = []
    trend_weeks = max(2, int(trend_period_weeks))
    latest_week = weekly_df['week'].max()

    for sku in weekly_df['sku'].unique():
        group = weekly_df[weekly_df['sku'] == sku].sort_values('week')
        recent = group.tail(trend_weeks)

        if recent.empty:
            last_week_sales = 0
            last_month_sales = 0
            whole_period_sales = 0
            trend = 1
            forecast_1w = 0
            forecast_4w = 0
        else:
            whole_period_sales = recent['outbound'].sum()
            trend, forecast_1w, forecast_4w = _linear_weekly_forecast(recent['outbound'])

            if raw_df is not None:
                last_week_sales = get_last_n_days_sales(raw_df, sku, 7, reference_date=global_latest_date)
                last_month_sales = get_last_n_days_sales(raw_df, sku, 28, reference_date=global_latest_date)
            else:
                last_week_sales = group.iloc[-1]['outbound'] if not group.empty else 0
                last_month_sales = group.tail(4)['outbound'].sum() if len(group) >= 4 else group['outbound'].sum()

        forecasts.append({
            "sku": sku,
            "sales_last_week": last_week_sales,
            "sales_last_month": last_month_sales,
            "whole_period_sales": whole_period_sales,
            "trend_coef": trend,
            "forecast_next_week": forecast_1w,
            "forecast_next_month": forecast_4w,
        })

    result = pd.DataFrame(forecasts)
    result = result.assign(
        forecast_next_week=lambda df: np.ceil(df["forecast_next_week"]).astype(int),
        forecast_next_month=lambda df: np.ceil(df["forecast_next_month"]).astype(int),
    )[
        [
            "sku",
            "whole_period_sales",
            "sales_last_week",
            "sales_last_month",
            "trend_coef",
            "forecast_next_week",
            "forecast_next_month",
        ]
    ]

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
    if not cached.empty:
        return cached

    return calculate_trend_and_forecast(trend_period_weeks=trend_period_weeks)
