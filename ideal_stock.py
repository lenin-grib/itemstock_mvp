import pandas as pd
import numpy as np
from db_utils import get_current_stock, get_parameters
from cache_service import get_cached_ideal_stock, save_ideal_stock_cache, invalidate_ideal_stock_cache

# --- Константы ---
quote_multiplicator = 1.5
min_items_in_stock = 5


def _optimize_ideal_stock_dtypes(df):
    if df.empty:
        return df

    int_like_cols = [
        'current_stock',
        'ideal_stock', 'ideal_stock_2w', 'ideal_stock_3w', 'monthly_ideal_stock',
        'to_order_week', 'to_order_2w', 'to_order_3w', 'to_order_month',
        'forecast_interval_p1w', 'forecast_interval_p2w', 'forecast_interval_p3w', 'forecast_interval_p4w',
        'whole_period_forecast',
    ]
    float_like_cols = [
        'whole_period_sales',
        'sales_interval_m4w', 'sales_interval_m3w', 'sales_interval_m2w', 'sales_interval_m1w',
        'trend_coef',
    ]

    for col in int_like_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype('int32')

    for col in float_like_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype('float32')

    return df

def _find_sales_column(df):
    candidates = (
        "qty",
        "quantity",
        "quantity_sold",
        "sales",
        "sales_qty",
        "sold",
        "количество",
        "qty_sold",
    )
    return next((col for col in df.columns if col.lower() in candidates), None)


def calculate_ideal_stock(
    forecast_df=None,
    stock_df=None,
    sales_df=None,
    quote_multiplicator=None,
    min_items_in_stock=None,
):
    """
    forecast_df: DataFrame с прогнозами (если None, загружает из БД)
    stock_df: DataFrame с текущими остатками (если None, загружает из БД)
    sales_df: полный файл продаж с колонками sku, date и количеством
    """

    params = get_parameters()
    trend_weeks = int(params.get('trend_period_weeks', int(params.get('trend_period_months', 2) * 4)))

    if forecast_df is None:
        from forecast import get_forecasts
        forecast_df = get_forecasts(trend_period_weeks=trend_weeks)

    if stock_df is None:
        stock_df = get_current_stock()

    # Ensure stock_df always has the required columns even when empty
    if 'sku' not in stock_df.columns:
        stock_df = pd.DataFrame(columns=['sku', 'current_stock'])

    if quote_multiplicator is None or min_items_in_stock is None:
        quote_multiplicator = params.get('quote_multiplicator', 1.5)
        min_items_in_stock = params.get('min_items_in_stock', 5)

    df = forecast_df.merge(stock_df, on="sku", how="left")
    df["current_stock"] = df["current_stock"].fillna(0).astype(int)

    # Calculate cumulative forecasts from individual intervals
    # Individual intervals: forecast_interval_p1w, forecast_interval_p2w, forecast_interval_p3w, forecast_interval_p4w
    # Cumulative: 1w, 2w, 3w, 4w (for backward compatibility in calculations)
    if 'forecast_interval_p1w' in df.columns:
        df['forecast_1w_cumul'] = df['forecast_interval_p1w'].fillna(0)
        df['forecast_2w_cumul'] = (
            df.get('forecast_interval_p1w', 0).fillna(0) +
            df.get('forecast_interval_p2w', 0).fillna(0)
        )
        df['forecast_3w_cumul'] = (
            df.get('forecast_interval_p1w', 0).fillna(0) +
            df.get('forecast_interval_p2w', 0).fillna(0) +
            df.get('forecast_interval_p3w', 0).fillna(0)
        )
        df['forecast_4w_cumul'] = df.get('whole_period_forecast', 0).fillna(0)
    else:
        # Fallback for old data format (shouldn't happen after migration)
        df['forecast_1w_cumul'] = df.get('forecast_next_week', 0).fillna(0)
        df['forecast_2w_cumul'] = df.get('forecast_2w', 0).fillna(0)
        df['forecast_3w_cumul'] = df.get('forecast_3w', 0).fillna(0)
        df['forecast_4w_cumul'] = df.get('forecast_next_month', 0).fillna(0)

    # идеальный запас
    df["ideal_stock"] = df["forecast_1w_cumul"] * quote_multiplicator + min_items_in_stock
    df.loc[df["forecast_4w_cumul"] == 0, "ideal_stock"] = 0
    df["ideal_stock"] = np.ceil(df["ideal_stock"]).astype(int)

    df["monthly_ideal_stock"] = (
        np.ceil(df["forecast_4w_cumul"] * quote_multiplicator + min_items_in_stock)
        .astype(int)
    )
    df.loc[df["forecast_4w_cumul"] == 0, "monthly_ideal_stock"] = 0

    # 2-week and 3-week ideal stocks
    for n_weeks, fc_col, is_col in [
        (2, 'forecast_2w_cumul', 'ideal_stock_2w'),
        (3, 'forecast_3w_cumul', 'ideal_stock_3w'),
    ]:
        if fc_col in df.columns:
            df[is_col] = np.ceil(df[fc_col] * quote_multiplicator + min_items_in_stock).astype(int)
            df.loc[df[fc_col] == 0, is_col] = 0
        else:
            df[is_col] = df['ideal_stock']

    # если есть данные о продажах, корректируем по недавним продажам
    if sales_df is not None and "date" in sales_df.columns:
        sales_col = _find_sales_column(sales_df)
        if sales_col is not None:
            cutoff = sales_df["date"].max() - pd.DateOffset(weeks=trend_weeks)

            recent_sales = sales_df.loc[sales_df["date"] >= cutoff]
            if not recent_sales.empty:
                recent_sales = recent_sales.groupby("sku")[sales_col].sum().reset_index()
                recent_sales = recent_sales.rename(columns={sales_col: "recent_qty"})

                df = df.merge(recent_sales, on="sku", how="left")
                df["recent_qty"] = df["recent_qty"].fillna(0)
                df.loc[df["recent_qty"] == 0, "ideal_stock"] = 0
                df.loc[df["recent_qty"] == 0, "ideal_stock_2w"] = 0
                df.loc[df["recent_qty"] == 0, "ideal_stock_3w"] = 0
                df.loc[df["recent_qty"] == 0, "monthly_ideal_stock"] = 0
                df = df.drop(columns=["recent_qty"])

    df["to_order_week"] = df["ideal_stock"] - df["current_stock"]
    df["to_order_week"] = np.ceil(df["to_order_week"]).astype(int)
    df["to_order_week"] = df["to_order_week"].clip(lower=0)

    df["to_order_2w"] = (df["ideal_stock_2w"] - df["current_stock"]).clip(lower=0)
    df["to_order_2w"] = np.ceil(df["to_order_2w"]).astype(int)

    df["to_order_3w"] = (df["ideal_stock_3w"] - df["current_stock"]).clip(lower=0)
    df["to_order_3w"] = np.ceil(df["to_order_3w"]).astype(int)

    df["to_order_month"] = df["monthly_ideal_stock"] - df["current_stock"]
    df["to_order_month"] = np.ceil(df["to_order_month"]).astype(int)
    df["to_order_month"] = df["to_order_month"].clip(lower=0)

    # Ensure unique SKU
    df = df.drop_duplicates(subset='sku')

    # Drop temporary cumulative forecast columns before saving to cache
    temp_cols = ['forecast_1w_cumul', 'forecast_2w_cumul', 'forecast_3w_cumul', 'forecast_4w_cumul']
    df = df.drop(columns=[col for col in temp_cols if col in df.columns])
    df = _optimize_ideal_stock_dtypes(df)

    # Save to cache
    save_ideal_stock_cache(df)

    return df


def get_ideal_stock():
    """
    Возвращает идеальный сток из кэша или рассчитывает новый
    """
    cached = get_cached_ideal_stock()
    if not cached.empty:
        return cached

    return calculate_ideal_stock()