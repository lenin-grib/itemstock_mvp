import pandas as pd
import streamlit as st

st.set_page_config(layout="wide")

from database import init_db
from forecast_schema import build_forecast_display_df
from sales_view_service import get_default_popular_threshold
from ui_helpers import (
    file_type_and_name,
    format_file_date_range,
    format_rub_amount,
    format_delivery_time_ru,
    parse_trend_weeks,
)
from sales_tab_controller import (
    get_uploaded_file_metadata,
    process_logs_upload,
    process_spoils_upload,
    load_forecast_and_stock,
    prepare_sales_view_data,
    validate_and_refresh_forecast,
)
from orders_tab_controller import (
    process_price_list_upload,
    load_ideal_stock_data,
    prepare_order_display_data,
    build_orders_view,
    refresh_orders_cache,
)
from suppliers_tab_controller import (
    load_suppliers_data,
    process_supplier_changes,
)
from params_tab_controller import (
    load_parameters,
    normalize_trend_period,
    validate_and_save_parameters,
    process_database_reset,
)

# Initialize database
init_db()

st.title("📦 Прогноз закупок")

# Load metadata
normalized_files, has_logs, has_spoils, has_price, latest_logs_date = get_uploaded_file_metadata()

# Display uploaded files
if normalized_files:
    with st.expander("📁 Загруженные файлы"):
        file_data = []
        for file_id, filename, file_type, upload_date, date_from, date_to in normalized_files:
            source_label, display_name = file_type_and_name(file_type, filename)
            date_range = format_file_date_range(source_label, upload_date, date_from, date_to)
            file_data.append([file_id, display_name, source_label, date_range])

        if file_data:
            files_df = pd.DataFrame(file_data, columns=["ID", "Название", "Тип", "Диапазон дат"])
            st.dataframe(files_df, height=200, use_container_width=True)
else:
    with st.expander("📁 Загрузки"):
        st.info("Загрузите файлы в соответствующих вкладках")

# Parameters (always available)
params = load_parameters()

tab_sales, tab_orders, tab_suppliers, tab_params = st.tabs(
    ["Продажи и прогноз", "Склад и заказы", "Поставщики", "Параметры"]
)

# Initialize session state
if 'processed_log_upload_signatures' not in st.session_state:
    st.session_state['processed_log_upload_signatures'] = set()
if 'logs_uploader_selection_signatures' not in st.session_state:
    st.session_state['logs_uploader_selection_signatures'] = tuple()
if 'processed_spoils_upload_signature' not in st.session_state:
    st.session_state['processed_spoils_upload_signature'] = None
if 'processed_price_upload_signature' not in st.session_state:
    st.session_state['processed_price_upload_signature'] = None
if 'reset_db_requested' not in st.session_state:
    st.session_state['reset_db_requested'] = False

# Load core data
trend_weeks_raw = normalize_trend_period(params)
trend_weeks, trend_weeks_validation_error = parse_trend_weeks(trend_weeks_raw)
if trend_weeks_validation_error:
    trend_weeks = 2

forecast_df, stock_df = load_forecast_and_stock(trend_weeks)
ideal_stock_df, _ = load_ideal_stock_data()

# ============================================================================
# SALES TAB
# ============================================================================
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

    current_logs_sigs = tuple(sorted(
        getattr(f, 'file_id', '') + "|" + getattr(f, 'name', '') + "|" + str(getattr(f, 'size', ''))
        for f in (uploaded_files or [])
    ))
    
    if current_logs_sigs != st.session_state.get('logs_uploader_selection_signatures', tuple()):
        st.session_state['logs_uploader_selection_signatures'] = current_logs_sigs
        st.session_state['processed_log_upload_signatures'] = set()

    if uploaded_files:
        updated_sigs, logs_changed, error_msg = process_logs_upload(
            uploaded_files,
            st.session_state['processed_log_upload_signatures']
        )
        st.session_state['processed_log_upload_signatures'] = updated_sigs
        if error_msg:
            st.error(error_msg)
        elif logs_changed:
            st.rerun()

    if spoils_file is not None:
        new_sig, spoils_changed, error_msg = process_spoils_upload(
            spoils_file,
            st.session_state.get('processed_spoils_upload_signature')
        )
        st.session_state['processed_spoils_upload_signature'] = new_sig
        if error_msg:
            st.error(error_msg)
        elif spoils_changed:
            st.rerun()

    st.divider()

    if has_spoils and not has_logs:
        st.warning(
            "Загружен файл списаний, но не загружены файлы логов. "
            "Загрузите логи, чтобы корректно рассчитать net sales и прогноз."
        )

    if not has_spoils:
        st.warning(
            "Прогноз сейчас рассчитывается без учета списаний. "
            "Пожалуйста, загрузите файл списаний."
        )

    if not forecast_df.empty:
        st.subheader("📈 Прогноз продаж")

        if trend_weeks_validation_error:
            st.warning(
                "Параметр периода тренда в БД невалиден. "
                "Используется безопасное значение 2 недели. "
                f"Детали: {trend_weeks_validation_error}"
            )

        whole_period_days = max(1, trend_weeks * 7)

        col1, col2 = st.columns([3, 1])
        with col1:
            st.write("")
        with col2:
            if st.button("Обновить прогноз", key="refresh_forecast"):
                recalc_errors, should_rerun = validate_and_refresh_forecast(trend_weeks, latest_logs_date)
                if recalc_errors:
                    for err in recalc_errors:
                        st.error(err)
                elif should_rerun:
                    st.success("Кэш прогноза очищен, выполняется перерасчет")
                    st.rerun()

        if latest_logs_date is not None:
            st.info(
                f"В прогнозе учтены данные логов по дату: {latest_logs_date.strftime('%d.%m.%Y')}"
            )
        else:
            st.info("В прогнозе пока нет даты из обработанных файлов логов.")

        st.caption(
            f"Сейчас прогноз и whole_period_sales рассчитываются по данным за последние "
            f"{trend_weeks} нед. ({whole_period_days} дней). Изменить период можно во вкладке "
            f"\"Параметры\"."
        )

        display_forecast_df = forecast_df.copy()
        display_forecast_df = build_forecast_display_df(display_forecast_df)
        st.dataframe(display_forecast_df)

        popular_threshold = st.number_input(
            "Порог популярности (продаж за период)",
            min_value=0,
            value=get_default_popular_threshold(trend_weeks),
            step=1
        )

        sales_view_model = prepare_sales_view_data(forecast_df, stock_df, popular_threshold)
        popular = sales_view_model.popular_df
        no_demand = sales_view_model.no_demand_df

        col_popular, col_no_demand = st.columns([3, 2])
        with col_popular:
            st.subheader("🔥 Популярные товары")
            st.dataframe(popular.head(20), height=320, use_container_width=True)
        with col_no_demand:
            st.subheader("😴 Товары без спроса")
            st.dataframe(no_demand, height=320, use_container_width=True)
    else:
        st.warning("Нет данных для прогноза")

# ============================================================================
# ORDERS TAB
# ============================================================================
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
        new_sig, price_changed, error_msg = process_price_list_upload(
            price_list_file,
            st.session_state.get('processed_price_upload_signature')
        )
        st.session_state['processed_price_upload_signature'] = new_sig
        if error_msg:
            st.error(error_msg)
        elif price_changed:
            st.rerun()

    st.divider()

    if has_price and not has_logs:
        st.warning(
            "Загружен прайс-лист, но не загружены файлы логов. "
            "Сначала загрузите логи, чтобы сформировать основной список товаров и корректные заказы."
        )

    if not ideal_stock_df.empty:
        st.subheader("📦 Склад")

        col1, col2 = st.columns([3, 1])
        with col1:
            st.write("")
        with col2:
            if st.button("Обновить заказы", key="refresh_orders"):
                refresh_orders_cache()
                st.success("Кэш заказов очищен, выполняется перерасчет")
                st.rerun()

        order_df, active_to_order, active_ideal = prepare_order_display_data(ideal_stock_df, order_period_weeks)
        
        if not order_df.empty:
            def highlight_row(row):
                to_order_value = float(row.get(active_to_order, 0) or 0)
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
                active_ideal,
                active_to_order,
            ]].style.apply(highlight_row, axis=1)

            st.dataframe(styled_df)

            st.subheader("🧾 Рекомендуемые заказы")
            orders_view = build_orders_view(order_df, order_period_weeks)
            recommended_orders = orders_view.recommended_orders
            missing_supplier_skus = orders_view.missing_supplier_skus
            below_min_map = orders_view.below_min_map
            zero_price_map = orders_view.zero_price_map

            if missing_supplier_skus:
                st.warning("Не найден поставщик для следующих товаров:")
                st.dataframe(pd.DataFrame({'Товар': missing_supplier_skus}), height=140, use_container_width=True)

            if recommended_orders:
                for order in recommended_orders:
                    has_min_warning = order['supplier_name'] in below_min_map
                    has_zero_price_warning = order['supplier_name'] in zero_price_map
                    has_no_supplier_warning = bool(order.get('is_without_supplier'))
                    if has_no_supplier_warning:
                        label = f"❗ Без поставщика | {format_rub_amount(order['total_cost'])} ₽"
                    else:
                        base_label = (
                            f"{order['supplier_name']} | "
                            f"{format_rub_amount(order['total_cost'])} ₽ | "
                            f"Срок: {format_delivery_time_ru(order['delivery_time'])}"
                        )
                        label = f"❗ {base_label}" if (has_min_warning or has_zero_price_warning) else base_label

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
                        if has_zero_price_warning:
                            zero_warn = zero_price_map[order['supplier_name']]
                            items_text = ", ".join(zero_warn['items'])
                            st.warning(
                                "Для одного или нескольких товаров в загруженном прайс-листе указана нулевая цена: "
                                f"{items_text}."
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

# ============================================================================
# SUPPLIERS TAB
# ============================================================================
with tab_suppliers:
    st.subheader("🧾 Поставщики")

    suppliers_df, display_df = load_suppliers_data()
    
    if not suppliers_df.empty:
        edited = st.data_editor(
            display_df,
            num_rows='fixed',
            use_container_width=True,
            column_config={
                'Название': st.column_config.Column(disabled=True)
            }
        )

        has_changes, changes, error_msg = process_supplier_changes(display_df, edited)
        
        if error_msg:
            st.error(error_msg)
        elif has_changes:
            col1, col2 = st.columns(2)
            with col1:
                if st.button('Сохранить изменения'):
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

# ============================================================================
# PARAMETERS TAB
# ============================================================================
with tab_params:
    st.subheader("Параметры расчёта")
    
    if trend_weeks_validation_error:
        st.warning(
            "Текущее значение периода тренда невалидно и будет заменено при сохранении. "
            f"Детали: {trend_weeks_validation_error}"
        )
    
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
        min_value=2,
        value=trend_weeks,
        step=1
    )
    st.caption("Допустимо только целое положительное значение, минимум 2.")

    if st.button("Сохранить параметры"):
        is_valid, error_msg, should_rerun = validate_and_save_parameters(
            new_quote,
            new_min_stock,
            new_trend_period
        )
        if not is_valid:
            st.error(error_msg)
        else:
            st.success("✓ Параметры сохранены")
            st.info("Выполняется пересчет прогнозов и всех связанных таблиц...")
            st.rerun()

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

    if st.button("Сбросить БД", type="primary"):
        st.session_state.pop('confirm_reset_db', None)
        st.session_state['reset_db_requested'] = True

    if st.session_state.get('reset_db_requested'):
        st.error("Вы действительно хотите полностью очистить базу данных? Это действие необратимо.")
        confirm_reset = st.checkbox("Да, подтверждаю полный сброс БД", key="confirm_reset_db")
        col_confirm, col_cancel = st.columns(2)

        with col_confirm:
            if st.button("Подтвердить сброс", type="primary", disabled=not confirm_reset):
                success, error_msg = process_database_reset()
                if success:
                    st.session_state['reset_db_requested'] = False
                    st.success("База данных успешно сброшена")
                    st.rerun()
                else:
                    st.error(error_msg)

        with col_cancel:
            if st.button("Отмена сброса"):
                st.session_state['reset_db_requested'] = False
                st.rerun()
