import pandas as pd
import streamlit as st

st.set_page_config(layout="wide")

from db_utils import get_parameters, get_uploaded_files, update_parameter, get_all_skus
from parser import parse_and_save_file, parse_and_save_spoils_file
from forecast import get_forecasts
from ideal_stock import get_ideal_stock, calculate_ideal_stock
from supplier_service import save_supplier_file, get_suppliers, update_supplier_info
from cache_service import invalidate_forecast_cache, invalidate_ideal_stock_cache
from database import init_db

# Initialize database
init_db()

st.title("📦 Прогноз закупок")

# Show uploaded files
all_uploaded_files = get_uploaded_files()
uploaded_log_files = [f for f in all_uploaded_files if not str(f[1]).startswith('spoils::')]
uploaded_filenames = [f[1] for f in uploaded_log_files] if uploaded_log_files else []
if all_uploaded_files:
    with st.expander("📁 Загруженные файлы"):
        # Compute date range for each file
        file_data = []
        for file_id, filename, upload_date, date_from, date_to in all_uploaded_files:
            is_spoil_file = str(filename).startswith('spoils::')
            display_name = str(filename).replace('spoils::', '', 1) if is_spoil_file else filename
            source_label = "Списания" if is_spoil_file else "Логи"

            if date_from and date_to:
                date_range = f"{date_from.strftime('%d.%m.%Y')} - {date_to.strftime('%d.%m.%Y')}"
            else:
                date_range = "Нет данных"
            file_data.append([file_id, display_name, source_label, date_range])

        files_df = pd.DataFrame(file_data, columns=["ID", "Название", "Тип", "Диапазон дат"])

        col1, col2 = st.columns([2, 1])
        with col1:
            st.dataframe(files_df, height=200, width='stretch')
        with col2:
            # Upload new files
            uploaded_files = st.file_uploader(
                "Загрузить новые файлы логов",
                type=["xlsx"],
                accept_multiple_files=True
            )
            spoils_file = st.file_uploader(
                "Загрузить историю списаний",
                type=["xlsx"],
                key="spoils_file"
            )
else:
    with st.expander("📁 Загрузки"):
        # Upload new files
        uploaded_files = st.file_uploader(
            "Загрузить новые файлы логов",
            type=["xlsx"],
            accept_multiple_files=True
        )
        spoils_file = st.file_uploader(
            "Загрузить историю списаний",
            type=["xlsx"],
            key="spoils_file"
        )

if uploaded_files:
    for file in uploaded_files:
        if file.name in uploaded_filenames:
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"Обновить {file.name}", key=f"update_{file.name}"):
                    try:
                        parse_and_save_file(file)
                        invalidate_forecast_cache()
                        invalidate_ideal_stock_cache()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка при обновлении файла {file.name}: {str(e)}")
            with col2:
                st.info(f"Файл {file.name} уже загружен. Нажмите 'Обновить' для замены данных.")
        else:
            try:
                parse_and_save_file(file)
                # Invalidate caches
                invalidate_forecast_cache()
                invalidate_ideal_stock_cache()
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка при обработке файла {file.name}: {str(e)}")
    if any(file.name in uploaded_filenames for file in uploaded_files):
        st.rerun()

if spoils_file is not None:
    try:
        parse_and_save_spoils_file(spoils_file)
        invalidate_forecast_cache()
        invalidate_ideal_stock_cache()
        st.rerun()
    except Exception as e:
        st.error(f"Ошибка при обработке файла списаний {spoils_file.name}: {str(e)}")

# Parameters (always available)
params = get_parameters()

tab_sales, tab_orders, tab_suppliers, tab_params = st.tabs(
    ["Продажи и прогноз", "Склад и заказы", "Поставщики", "Параметры"]
)

# Load data for tabs (always render tabs, even right after uploads/reruns)
trend_weeks = int(params.get('trend_period_weeks', int(params.get('trend_period_months', 2) * 4)))
forecast_df = get_forecasts(trend_period_weeks=trend_weeks)

# Get current stock
from db_utils import get_current_stock
stock_df = get_current_stock()

# Calculate ideal stock
ideal_stock_df = get_ideal_stock()

with tab_sales:
    if not forecast_df.empty:
            st.subheader("📈 Прогноз продаж")

            col1, col2 = st.columns([3, 1])
            with col1:
                st.write("")
            with col2:
                if st.button("Обновить прогноз", key="refresh_forecast"):
                    invalidate_forecast_cache()
                    st.success("Кэш прогноза очищен, выполняется перерасчет")
                    st.rerun()

            st.dataframe(forecast_df)

            # Popular and no-demand items: use same period metric as forecast table
            period_weeks = int(params.get('trend_period_weeks', int(params.get('trend_period_months', 2) * 4)))
            all_skus = get_all_skus()

            sales_view = forecast_df[['sku', 'whole_period_sales', 'forecast_next_month']].copy()
            sales_view['net_sales_period'] = pd.to_numeric(sales_view['whole_period_sales'], errors='coerce').fillna(0)
            sales_view = sales_view.merge(
                stock_df[['sku', 'current_stock']],
                on='sku',
                how='left'
            )
            sales_view['current_stock'] = sales_view['current_stock'].fillna(0)

            popular_threshold = st.number_input(
                "Порог популярности (продаж за период)",
                min_value=0,
                value=max(1, int(35 * (period_weeks / 4))),
                step=1
            )

            popular = sales_view.loc[
                sales_view["net_sales_period"] > popular_threshold,
                ["sku", "net_sales_period", "current_stock", "forecast_next_month"]
            ].sort_values("net_sales_period", ascending=False)

            popular = popular.rename(columns={
                'sku': 'Товар',
                'net_sales_period': 'Продажи за период',
                'current_stock': 'Осталось на складе',
                'forecast_next_month': 'Прогноз на следующий месяц'
            })

            no_demand = sales_view.loc[sales_view["net_sales_period"] == 0, ["sku"]]

            existing = set(no_demand['sku'])
            for sku in all_skus:
                if sku not in set(sales_view['sku']) and sku not in existing:
                    no_demand = pd.concat([no_demand, pd.DataFrame([{'sku': sku}])], ignore_index=True)

            col_popular, col_no_demand = st.columns(2)
            with col_popular:
                st.subheader("🔥 Популярные товары")
                st.dataframe(popular.head(20), height=320, width='stretch')
            with col_no_demand:
                st.subheader("😴 Товары без спроса")
                st.dataframe(no_demand, height=320, width='stretch')
    else:
        st.warning("Нет данных для прогноза")

with tab_orders:
    if not ideal_stock_df.empty:
            st.subheader("📦 Заказы")

            col1, col2 = st.columns([3, 1])
            with col1:
                st.write("")
            with col2:
                if st.button("Обновить заказы", key="refresh_orders"):
                    invalidate_ideal_stock_cache()
                    st.success("Кэш заказов очищен, выполняется перерасчет")
                    st.rerun()

            order_df = ideal_stock_df.loc[ideal_stock_df["to_order_week"] > 0]
            if not order_df.empty:
                def highlight_row(row):
                    if row['current_stock'] == 0:
                        return ['background-color: rgba(255, 0, 0, 0.3)'] * len(row)
                    if row['current_stock'] <= row['monthly_ideal_stock'] / 8:
                        return ['background-color: rgba(255, 0, 0, 0.3)'] * len(row)
                    if row['current_stock'] <= row['monthly_ideal_stock'] / 4:
                        return ['background-color: rgba(255, 255, 0, 0.3)'] * len(row)
                    return [''] * len(row)

                styled_df = order_df[[
                    "sku",
                    "current_stock",
                    "monthly_ideal_stock",
                    "to_order_month"
                ]].style.apply(highlight_row, axis=1)

                st.dataframe(styled_df)
            else:
                st.info("Нет товаров для заказа на эту неделю")
    else:
        st.warning("Нет данных об остатках")

with tab_suppliers:
    st.subheader("🧾 Поставщики")

    supplier_file = st.file_uploader(
        "Загрузить файл поставщиков",
        type=["xlsx"],
        key="supplier_file"
    )

    if supplier_file is not None:
        try:
            save_supplier_file(supplier_file)
            st.rerun()
        except Exception as e:
            st.error(f"Ошибка при обработке файла поставщиков: {str(e)}")

    suppliers_df = get_suppliers()
    if not suppliers_df.empty:
        display_df = suppliers_df[[
            'name',
            'delivery_cost',
            'delivery_time',
            'min_order'
        ]].rename(columns={
            'name': 'Название',
            'delivery_cost': 'Стоимость доставки',
            'delivery_time': 'Срок доставки',
            'min_order': 'Минимальный заказ'
        })

        edited = st.data_editor(
            display_df,
            num_rows='fixed',
            width='stretch',
            column_config={
                'Название': st.column_config.Column(disabled=True)
            }
        )

        # Check for changes and highlight in editor
        original_values = display_df.set_index('Название')
        edited_values = edited.set_index('Название')
        changes = {}
        for name in original_values.index:
            if name in edited_values.index:
                orig_row = original_values.loc[name]
                edit_row = edited_values.loc[name]
                changed_cols = []
                for col in ['Стоимость доставки', 'Срок доставки', 'Минимальный заказ']:
                    if orig_row[col] != edit_row[col]:
                        changed_cols.append(col)
                if changed_cols:
                    changes[name] = changed_cols

        if changes:
            col1, col2 = st.columns(2)
            with col1:
                if st.button('Сохранить изменения'):
                    edited = edited.rename(columns={
                        'Название': 'name',
                        'Стоимость доставки': 'delivery_cost',
                        'Срок доставки': 'delivery_time',
                        'Минимальный заказ': 'min_order'
                    })
                    for _, row in edited.iterrows():
                        update_supplier_info(
                            row['name'],
                            row['delivery_cost'],
                            row['delivery_time'],
                            row['min_order']
                        )
                    st.success('Изменения поставщиков сохранены')
                    st.rerun()
            with col2:
                if st.button('Отменить изменения'):
                    st.rerun()
        else:
            if st.button('Сохранить изменения поставщиков'):
                st.info('Нет изменений для сохранения')
    else:
        st.info("Нет данных по поставщикам")

with tab_params:
    st.subheader("Параметры расчёта")
    new_quote = st.number_input(
        "Коэффициент запаса",
        min_value=0.1,
        value=float(params.get('quote_multiplicator', 1.5)),
        step=0.1,
        format="%.2f",
    )
    new_min_stock = st.number_input(
        "Минимальный запас на складе",
        min_value=0,
        value=int(params.get('min_items_in_stock', 5)),
        step=1
    )
    new_trend_period = st.number_input(
        "Период для расчёта тренда (недели)",
        min_value=1,
        value=int(params.get('trend_period_weeks', int(params.get('trend_period_months', 2) * 4))),
        step=1
    )

    if st.button("Сохранить параметры"):
        update_parameter('quote_multiplicator', new_quote)
        update_parameter('min_items_in_stock', new_min_stock)
        update_parameter('trend_period_weeks', new_trend_period)
        invalidate_forecast_cache()
        invalidate_ideal_stock_cache()
        st.success("Параметры сохранены")
        st.rerun()