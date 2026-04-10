import pandas as pd
import numpy as np

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
    forecast_df,
    stock_df,
    sales_df=None,
    quote_multiplicator=quote_multiplicator,
    min_items_in_stock=min_items_in_stock,
):
    """
    forecast_df:
        sku, forecast_next_week, forecast_next_month

    stock_df:
        sku, current_stock

    sales_df:
        полный файл продаж с колонками sku, date и количеством
    """

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

    if sales_df is not None:
        sales_col = _find_sales_column(sales_df)
        if sales_col is not None and "date" in sales_df.columns:
            cutoff = sales_df["date"].max() - pd.DateOffset(months=2)
            recent_sales = (
                sales_df.loc[sales_df["date"] >= cutoff]
                .groupby("sku", as_index=False)[sales_col]
                .sum()
            )
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

    return df