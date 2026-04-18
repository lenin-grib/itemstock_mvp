import pandas as pd
import streamlit as st

st.set_page_config(layout="wide")

from db_utils import get_parameters, get_uploaded_files, update_parameter, update_parameters, reset_database_data, get_all_skus
from parser import parse_and_save_file, parse_and_save_spoils_file, parse_and_save_price_list_file
from forecast import get_forecasts
from ideal_stock import get_ideal_stock, calculate_ideal_stock
from order_service import build_recommended_orders
from supplier_service import save_supplier_file, get_suppliers, update_supplier_info
from cache_service import invalidate_forecast_cache, invalidate_ideal_stock_cache
from database import init_db

# Initialize database
init_db()

st.title("📦 Прогноз закупок")

# Show uploaded files
all_uploaded_files = get_uploaded_files()


def _normalize_uploaded_file_row(row):
    """Supports both legacy 5-field and new 6-field tuple formats."""
    if len(row) == 6:
        file_id, filename, file_type, upload_date, date_from, date_to = row
        return file_id, filename, (file_type or 'logs'), upload_date, date_from, date_to
    if len(row) == 5:
        file_id, filename, upload_date, date_from, date_to = row
        return file_id, filename, 'logs', upload_date, date_from, date_to
    raise ValueError(f"Unexpected uploaded file row format: {row}")


normalized_uploaded_files = [_normalize_uploaded_file_row(r) for r in all_uploaded_files]
uploaded_log_files = [
    f for f in normalized_uploaded_files
    if str(f[2] or 'logs') == 'logs'
]
latest_logs_processed_date = max(
    (f[5] for f in uploaded_log_files if f[5] is not None),
    default=None,
)
has_spoils_file = any(str(f[2] or 'logs') == 'spoils' for f in normalized_uploaded_files)
uploaded_filenames = [f[1] for f in uploaded_log_files] if uploaded_log_files else []


def _file_type_and_name(file_type, raw_filename):
    # Backward-compatible display: strip legacy prefixes if they are present in old rows.
    display_name = str(raw_filename)
    for prefix in ('spoils::', 'price::', 'suppliers::'):
        if display_name.startswith(prefix):
            display_name = display_name.replace(prefix, '', 1)
            break

    mapped = {
        'spoils': 'Списания',
        'price': 'Прайс-лист',
        'suppliers': 'Поставщики',
        'logs': 'Логи',
    }
    return mapped.get(str(file_type or 'logs'), 'Логи'), display_name


def _format_file_date_range(file_type, upload_date, date_from, date_to):
    if file_type in ("Прайс-лист", "Поставщики"):
        if upload_date:
            return upload_date.strftime('%d.%m.%Y')
        return "Нет данных"

    if date_from and date_to:
        return f"{date_from.strftime('%d.%m.%Y')} - {date_to.strftime('%d.%m.%Y')}"
    return "Нет данных"


def _format_rub_amount(value):
    try:
        return f"{float(value):,.2f}".replace(',', ' ')
    except (TypeError, ValueError):
        return str(value)


def _day_word_ru(days):
    days = abs(int(days))
    last_two = days % 100
    last_digit = days % 10
    if 11 <= last_two <= 14:
        return "дней"
    if last_digit == 1:
        return "день"
    if 2 <= last_digit <= 4:
        return "дня"
    return "дней"


def _format_delivery_time_ru(delivery_time):
    if delivery_time is None:
        return "не указан"

    raw_value = str(delivery_time).strip()
    if not raw_value:
        return "не указан"

    try:
        numeric_value = float(raw_value.replace(',', '.'))
    except ValueError:
        return raw_value

    if numeric_value.is_integer():
        days = int(numeric_value)
        return f"{days} {_day_word_ru(days)}"

    return raw_value

if all_uploaded_files:
    with st.expander("📁 Загруженные файлы"):
        file_data = []
        for file_id, filename, file_type, upload_date, date_from, date_to in normalized_uploaded_files:
            source_label, display_name = _file_type_and_name(file_type, filename)
            date_range = _format_file_date_range(source_label, upload_date, date_from, date_to)
            file_data.append([file_id, display_name, source_label, date_range])

        files_df = pd.DataFrame(file_data, columns=["ID", "Название", "Тип", "Диапазон дат"])

        st.dataframe(files_df, height=200, use_container_width=True)
else:
    with st.expander("📁 Загрузки"):
        st.info("Загрузите файлы в соответствующих вкладках")

# Parameters (always available)
params = get_parameters()

tab_sales, tab_orders, tab_suppliers, tab_params = st.tabs(
    ["Продажи и прогноз", "Склад и заказы", "Поставщики", "Параметры"]
)

# Load data for tabs (always render tabs, even right after uploads/reruns)
trend_weeks = int(params.get('trend_period_weeks', int(params.get('trend_period_months', 2) * 4)))

_FORECAST_COLS = [
    'sku',
    'whole_period_sales',
    'sales_last_month', 'sales_last_3w', 'sales_last_2w', 'sales_last_week',
    'trend_coef',
    'forecast_next_week', 'forecast_2w', 'forecast_3w', 'forecast_next_month',
]
_IDEAL_STOCK_COLS = [
    'sku', 'current_stock',
    'ideal_stock', 'ideal_stock_2w', 'ideal_stock_3w', 'monthly_ideal_stock',
    'to_order_week', 'to_order_2w', 'to_order_3w', 'to_order_month',
]

try:
    forecast_df = get_forecasts(trend_period_weeks=trend_weeks)
except Exception as _exc:
    st.error(f"Ошибка при загрузке прогнозов: {_exc}")
    forecast_df = pd.DataFrame(columns=_FORECAST_COLS)

# Get current stock
from db_utils import get_current_stock
try:
    stock_df = get_current_stock()
except Exception as _exc:
    st.error(f"Ошибка при загрузке остатков: {_exc}")
    stock_df = pd.DataFrame(columns=['sku', 'current_stock'])

# Calculate ideal stock
try:
    ideal_stock_df = get_ideal_stock()
except Exception as _exc:
    st.error(f"Ошибка при расчёте идеального стока: {_exc}")
    ideal_stock_df = pd.DataFrame(columns=_IDEAL_STOCK_COLS)

with tab_sales:
    st.subheader("📥 Загрузка логов и списаний")
    uploaded_files = st.file_uploader(
        "Загрузить новые файлы логов",
        type=["xlsx"],
        accept_multiple_files=True,
        key="logs_uploader"
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

    st.divider()

    if not has_spoils_file:
        st.warning(
            "Прогноз сейчас рассчитывается без учета списаний. "
            "Пожалуйста, загрузите файл списаний."
        )

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

            if latest_logs_processed_date is not None:
                st.info(
                    f"В прогнозе учтены данные логов по дату: {latest_logs_processed_date.strftime('%d.%m.%Y')}"
                )
            else:
                st.info("В прогнозе пока нет даты из обработанных файлов логов.")

            display_forecast_df = forecast_df.copy()
            if 'last_updated' in display_forecast_df.columns:
                display_forecast_df = display_forecast_df.drop(columns=['last_updated'])
            st.dataframe(display_forecast_df)

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

            col_popular, col_no_demand = st.columns([3, 2])
            with col_popular:
                st.subheader("🔥 Популярные товары")
                st.dataframe(popular.head(20), height=320, use_container_width=True)
            with col_no_demand:
                st.subheader("😴 Товары без спроса")
                st.dataframe(no_demand, height=320, use_container_width=True)
    else:
        st.warning("Нет данных для прогноза")

with tab_orders:
    st.subheader("📥 Загрузка прайс-листа")

    _period_labels = {
        "1 неделя": 1,
        "2 недели": 2,
        "3 недели": 3,
        "4 недели": 4,
    }
    _period_label = st.radio(
        "Период закупки",
        options=list(_period_labels.keys()),
        index=3,
        horizontal=True,
        key="order_period_radio",
    )
    order_period_weeks = _period_labels[_period_label]

    price_list_file = st.file_uploader(
        "Загрузить прайс-лист товаров",
        type=["xlsx"],
        key="price_list_file"
    )

    if price_list_file is not None:
        try:
            parse_and_save_price_list_file(price_list_file)
            st.rerun()
        except Exception as e:
            st.error(f"Ошибка при обработке прайс-листа {price_list_file.name}: {str(e)}")

    st.divider()

    if not ideal_stock_df.empty:
            st.subheader("📦 Склад")

            col1, col2 = st.columns([3, 1])
            with col1:
                st.write("")
            with col2:
                if st.button("Обновить заказы", key="refresh_orders"):
                    invalidate_ideal_stock_cache()
                    st.success("Кэш заказов очищен, выполняется перерасчет")
                    st.rerun()

            _period_to_order_col = {1: 'to_order_week', 2: 'to_order_2w', 3: 'to_order_3w', 4: 'to_order_month'}
            _period_ideal_col = {1: 'ideal_stock', 2: 'ideal_stock_2w', 3: 'ideal_stock_3w', 4: 'monthly_ideal_stock'}
            _active_to_order = _period_to_order_col.get(order_period_weeks, 'to_order_month')
            _active_ideal = _period_ideal_col.get(order_period_weeks, 'monthly_ideal_stock')
            if _active_to_order not in ideal_stock_df.columns:
                _active_to_order = 'to_order_month'
            if _active_ideal not in ideal_stock_df.columns:
                _active_ideal = 'monthly_ideal_stock'

            order_df = ideal_stock_df.loc[ideal_stock_df[_active_to_order] > 0]
            if not order_df.empty:
                def highlight_row(row):
                    to_order_value = float(row.get(_active_to_order, 0) or 0)
                    current_stock = float(row.get('current_stock', 0) or 0)

                    if current_stock == 0:
                        return ['background-color: rgba(255, 0, 0, 0.3)'] * len(row)
                    if to_order_value <= 0:
                        return [''] * len(row)

                    stock_to_order_ratio = current_stock / to_order_value
                    if stock_to_order_ratio <= 0.25:
                        return ['background-color: rgba(255, 0, 0, 0.3)'] * len(row)
                    if stock_to_order_ratio <= 0.5:
                        return ['background-color: rgba(255, 255, 0, 0.3)'] * len(row)
                    return [''] * len(row)

                styled_df = order_df[[
                    "sku",
                    "current_stock",
                    _active_ideal,
                    _active_to_order,
                ]].style.apply(highlight_row, axis=1)

                st.dataframe(styled_df)

                st.subheader("🧾 Рекомендуемые заказы")
                recommended_orders, missing_supplier_skus, below_min_warnings = build_recommended_orders(
                    order_df, period_weeks=order_period_weeks
                )

                if missing_supplier_skus:
                    st.warning("Не найден поставщик для следующих товаров:")
                    st.dataframe(pd.DataFrame({'Товар': missing_supplier_skus}), height=140, use_container_width=True)

                below_min_map = {
                    w['supplier_name']: w for w in below_min_warnings
                }

                if recommended_orders:
                    recommended_orders = sorted(
                        recommended_orders,
                        key=lambda x: (1 if x.get('is_without_supplier') else 0, -x['total_cost'])
                    )

                    for order in recommended_orders:
                        has_min_warning = order['supplier_name'] in below_min_map
                        has_no_supplier_warning = bool(order.get('is_without_supplier'))
                        if has_no_supplier_warning:
                            label = f"❗ Без поставщика | {_format_rub_amount(order['total_cost'])} ₽"
                        else:
                            base_label = (
                                f"{order['supplier_name']} | "
                                f"{_format_rub_amount(order['total_cost'])} ₽ | "
                                f"Срок: {_format_delivery_time_ru(order['delivery_time'])}"
                            )
                            label = f"❗ {base_label}" if has_min_warning else base_label

                        with st.expander(label, expanded=False):
                            if has_no_supplier_warning:
                                st.warning(
                                    "В прайс-листе указан поставщик 'Без поставщика' - "
                                    "эти позиции требуют назначения реального поставщика."
                                )
                            if has_min_warning:
                                warn = below_min_map[order['supplier_name']]
                                st.warning(
                                    "Сумма заказа без доставки ниже минимальной суммы заказа: "
                                    f"{warn['subtotal_without_delivery']:.2f} ₽ < {warn['min_order']:.2f} ₽"
                                )
                            st.write(
                                f"Стоимость товаров: {order['subtotal_without_delivery']:.2f} ₽ | "
                                f"Доставка: {order['delivery_cost']:.2f} ₽ | "
                                f"Итого: {order['total_cost']:.2f} ₽"
                            )
                            st.dataframe(pd.DataFrame(order['items']), use_container_width=True)
                else:
                    st.info("Недостаточно данных прайс-листа для формирования рекомендуемых заказов")
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
            use_container_width=True,
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
        value=float(params.get('quote_multiplicator', 1.0)),
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
        try:
            update_parameters({
                'quote_multiplicator': new_quote,
                'min_items_in_stock': new_min_stock,
                'trend_period_weeks': new_trend_period,
            })
            invalidate_forecast_cache()
            invalidate_ideal_stock_cache()
            st.success("Параметры сохранены")
            st.rerun()
        except Exception as e:
            st.error(f"Не удалось сохранить параметры: {e}")

    st.divider()
    st.markdown("### Опасная зона")

    st.markdown(
        """
        <style>
        div[data-testid="stBaseButton-primary"] {
            background-color: #c62828;
            border-color: #b71c1c;
            color: white;
        }
        div[data-testid="stBaseButton-primary"]:hover {
            background-color: #b71c1c;
            border-color: #8e0000;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if 'reset_db_requested' not in st.session_state:
        st.session_state['reset_db_requested'] = False

    if st.button("Сбросить БД", type="primary"):
        st.session_state.pop('confirm_reset_db', None)
        st.session_state['reset_db_requested'] = True

    if st.session_state.get('reset_db_requested'):
        st.error("Вы действительно хотите полностью очистить базу данных? Это действие необратимо.")
        confirm_reset = st.checkbox("Да, подтверждаю полный сброс БД", key="confirm_reset_db")
        col_confirm, col_cancel = st.columns(2)

        with col_confirm:
            if st.button("Подтвердить сброс", type="primary", disabled=not confirm_reset):
                try:
                    reset_database_data()
                    st.session_state['reset_db_requested'] = False
                    st.success("База данных успешно сброшена")
                    st.rerun()
                except Exception as e:
                    st.error(f"Не удалось сбросить БД: {e}")

        with col_cancel:
            if st.button("Отмена сброса"):
                st.session_state['reset_db_requested'] = False
                st.rerun()