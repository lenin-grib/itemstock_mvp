import pandas as pd
import numpy as np
from db_utils import get_current_stock, get_parameters
from cache_service import get_cached_ideal_stock, save_ideal_stock_cache, invalidate_ideal_stock_cache

# --- Константы ---
quote_multiplicator = 1.5
min_items_in_stock = 5

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

    if quote_multiplicator is None or min_items_in_stock is None:
        quote_multiplicator = params.get('quote_multiplicator', 1.5)
        min_items_in_stock = params.get('min_items_in_stock', 5)

    df = forecast_df.merge(stock_df, on="sku", how="left")
    df["current_stock"] = df["current_stock"].fillna(0)

    # идеальный запас
    df["ideal_stock"] = df["forecast_next_week"] * quote_multiplicator + min_items_in_stock
    df.loc[df["forecast_next_month"] == 0, "ideal_stock"] = 0
    df["ideal_stock"] = np.ceil(df["ideal_stock"]).astype(int)

    df["monthly_ideal_stock"] = (
        np.ceil(df["forecast_next_month"] * quote_multiplicator + min_items_in_stock)
        .astype(int)
    )
    df.loc[df["forecast_next_month"] == 0, "monthly_ideal_stock"] = 0

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
                df.loc[df["recent_qty"] == 0, "monthly_ideal_stock"] = 0
                df = df.drop(columns=["recent_qty"])

    df["to_order_week"] = df["ideal_stock"] - df["current_stock"]
    df["to_order_week"] = np.ceil(df["to_order_week"]).astype(int)
    df["to_order_week"] = df["to_order_week"].clip(lower=0)

    df["to_order_month"] = df["monthly_ideal_stock"] - df["current_stock"]
    df["to_order_month"] = np.ceil(df["to_order_month"]).astype(int)
    df["to_order_month"] = df["to_order_month"].clip(lower=0)

    # Ensure unique SKU
    df = df.drop_duplicates(subset='sku')

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