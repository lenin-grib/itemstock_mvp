import pandas as pd
import streamlit as st

st.set_page_config(layout="wide")

from parser import load_multiple_files, compute_inventory_balance
from forecast import calculate_sales_metrics, calculate_trend_and_forecast
from ideal_stock import calculate_ideal_stock, quote_multiplicator, min_items_in_stock

st.title("📦 Прогноз закупок")

uploaded_files = st.file_uploader(
    "Загрузи файлы логов",
    type=["xlsx"],
    accept_multiple_files=True
)

if uploaded_files:
    df = load_multiple_files(uploaded_files)

    if df.empty:
        st.warning("Нет данных")
        st.stop()

    metrics_df, weekly_df = calculate_sales_metrics(df)
    forecast_df = calculate_trend_and_forecast(weekly_df).sort_values("sku")

    stock_df = (
        df.sort_values("date")
        .groupby("sku")
        .tail(1)[["sku", "остаток на складе"]]
        .rename(columns={"остаток на складе": "current_stock"})
        .sort_values("sku")
    )

    tab_sales, tab_orders, tab_params = st.tabs(
        ["Продажи и прогноз", "Склад и заказы", "Параметры"]
    )

    with tab_params:
        st.subheader("Параметры расчёта")
        quote_multiplicator = st.number_input(
            "Коэффициент запаса",
            min_value=0.1,
            value=float(quote_multiplicator),
            step=0.1,
            format="%.2f",
        )
        min_items_in_stock = st.number_input(
            "Минимальное количество в запасе",
            min_value=0,
            value=int(min_items_in_stock),
            step=1,
        )
        trend_period_months = st.number_input(
            "Период тренда (месяцев)",
            min_value=1,
            max_value=12,
            value=2,
            step=1,
        )

        if "date" in df.columns:
            min_date = df["date"].min()
            max_date = df["date"].max()
            required_start = max_date - pd.DateOffset(months=trend_period_months)

            if min_date > required_start:
                st.warning(
                    f"В файле есть данные только с {min_date.date()} по {max_date.date()}, "
                    f"что меньше выбранного периода тренда {trend_period_months} мес. "
                    "Прогноз будет рассчитан, но может быть менее точным."
                )
        else:
            st.warning("Не найдена колонка date для проверки периода тренда.")

        st.write("Эти параметры применяются при расчёте `ideal_stock`.")

    forecast_df = calculate_trend_and_forecast(
        weekly_df,
        trend_period_months=trend_period_months,
    ).sort_values("sku")

    result = calculate_ideal_stock(
        forecast_df,
        stock_df,
        sales_df=df,
        quote_multiplicator=quote_multiplicator,
        min_items_in_stock=min_items_in_stock,
    )

    with tab_sales:
        st.subheader("📈 Прогноз")
        st.dataframe(forecast_df)

        popular_threshold = 35 * trend_period_months
        popular = forecast_df.loc[
            forecast_df["whole_period_sales"] >= popular_threshold,
            ["sku", "whole_period_sales"]
        ].sort_values("whole_period_sales", ascending=False)

        if not popular.empty:
            st.markdown(f"**Самые популярные за период (продажи >= {popular_threshold})**")
            st.dataframe(popular)

        no_demand = forecast_df.loc[
            forecast_df["whole_period_sales"] == 0, ["sku"]
        ].sort_values("sku")

        if not no_demand.empty:
            st.markdown("**Не пользуются спросом**")
            st.dataframe(no_demand)

    with tab_orders:
        st.subheader("🛒 Рекомендация к заказу")
        order_df = result[
            [
                "sku",
                "forecast_next_week",
                "forecast_next_month",
                "current_stock",
                "ideal_stock",
                "to_order",
            ]
        ].sort_values("sku")
        order_df = order_df.loc[order_df["to_order"] > 0]
        st.dataframe(order_df)