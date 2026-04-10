import pandas as pd
import numpy as np


def calculate_sales_metrics(df):
    """
    df: результат парсера (sku, date, outbound)

    Возвращает:
    DataFrame с метриками по каждому SKU
    """

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

    return result, weekly


def calculate_trend_and_forecast(weekly_df, trend_period_months=2):
    """
    weekly_df: sku, week, outbound
    trend_period_months: сколько месяцев истории использовать для прогноза
    """

    forecasts = []
    latest_week = weekly_df["week"].max()
    cutoff = latest_week - pd.DateOffset(months=trend_period_months)

    for sku, group in weekly_df.groupby("sku"):
        group = group.sort_values("week")
        recent = group.loc[group["week"] >= cutoff]

        if recent.empty:
            last_week_sales = 0
            last_month_sales = 0
            whole_period_sales = 0
            trend = 1
            forecast_1w = 0
            forecast_4w = 0
        else:
            whole_period_sales = recent["outbound"].sum()
            if len(recent) < 2:
                trend = 1
            else:
                first = recent.iloc[0]["outbound"]
                last = recent.iloc[-1]["outbound"]
                trend = 1 if first == 0 else last / first
            trend = max(0.5, min(trend, 1.5))
            avg_weekly = recent["outbound"].mean()
            forecast_1w = avg_weekly * trend
            forecast_4w = avg_weekly * trend * 4
            last_week_sales = recent.iloc[-1]["outbound"]
            last_month_sales = recent.tail(4)["outbound"].sum()

        forecasts.append({
            "sku": sku,
            "sales_last_week": last_week_sales,
            "sales_last_month": last_month_sales,
            "whole_period_sales": whole_period_sales,
            "trend_coef": trend,
            "forecast_next_week": forecast_1w,
            "forecast_next_month": forecast_4w,
        })

    return (
        pd.DataFrame(forecasts)
        .assign(
            forecast_next_week=lambda df: np.ceil(df["forecast_next_week"]).astype(int),
            forecast_next_month=lambda df: np.ceil(df["forecast_next_month"]).astype(int),
        )
        [
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
    )