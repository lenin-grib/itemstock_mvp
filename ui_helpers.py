"""
Shared UI helpers and formatting utilities for Streamlit presentation layer.
"""


def normalize_uploaded_file_row(row):
    """Supports both legacy 5-field and new 6-field tuple formats."""
    if len(row) == 6:
        file_id, filename, file_type, upload_date, date_from, date_to = row
        return file_id, filename, (file_type or 'logs'), upload_date, date_from, date_to
    if len(row) == 5:
        file_id, filename, upload_date, date_from, date_to = row
        return file_id, filename, 'logs', upload_date, date_from, date_to
    raise ValueError(f"Unexpected uploaded file row format: {row}")


def get_uploaded_file_signature(file_obj):
    """Generate a unique signature for an uploaded file."""
    if file_obj is None:
        return None
    file_id = getattr(file_obj, 'file_id', '')
    file_name = getattr(file_obj, 'name', '')
    file_size = getattr(file_obj, 'size', '')
    return f"{file_id}|{file_name}|{file_size}"


def file_type_and_name(file_type, raw_filename):
    """Format file type and name with backward-compatible prefix stripping."""
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


def format_file_date_range(file_type, upload_date, date_from, date_to):
    """Format date range for display."""
    if file_type in ("Прайс-лист", "Поставщики"):
        if upload_date:
            return upload_date.strftime('%d.%m.%Y')
        return "Нет данных"

    if date_from and date_to:
        return f"{date_from.strftime('%d.%m.%Y')} - {date_to.strftime('%d.%m.%Y')}"
    return "Нет данных"


def format_rub_amount(value):
    """Format amount as rubles with space separator."""
    try:
        return f"{float(value):,.2f}".replace(',', ' ')
    except (TypeError, ValueError):
        return str(value)


def day_word_ru(days):
    """Get correct Russian word for days (день/дня/дней)."""
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


def format_delivery_time_ru(delivery_time):
    """Format delivery time in Russian."""
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
        return f"{days} {day_word_ru(days)}"

    return raw_value


def parse_trend_weeks(value):
    """Parse and validate trend weeks parameter."""
    if value is None:
        return None, "Период тренда не задан. Допустимо только целое положительное значение, минимум 2."

    try:
        if isinstance(value, str):
            normalized = value.strip().replace(',', '.')
            numeric = float(normalized)
        else:
            numeric = float(value)
    except (TypeError, ValueError):
        return None, "Период тренда должен быть числом. Допустимо только целое положительное значение, минимум 2."

    if not numeric.is_integer():
        return None, "Период тренда должен быть целым числом. Минимум: 2."

    parsed = int(numeric)
    if parsed < 2:
        return None, "Период тренда должен быть не меньше 2 недель."

    return parsed, None


def validate_forecast_recalc_inputs(trend_weeks_value, latest_logs_date):
    """Validate inputs before forecast recalculation."""
    errors = []

    _, trend_error = parse_trend_weeks(trend_weeks_value)
    if trend_error:
        errors.append(trend_error)

    if latest_logs_date is None:
        errors.append("Нет загруженных логов с датами. Загрузите файл логов перед пересчетом прогноза.")

    try:
        from db_utils import get_net_sales_data
        net_sales_df = get_net_sales_data()
    except Exception as exc:
        errors.append(f"Не удалось проверить данные net sales: {exc}")
        return errors

    required_cols = {'sku', 'date', 'outbound'}
    missing_cols = required_cols - set(net_sales_df.columns)
    if missing_cols:
        errors.append(
            "В данных net sales отсутствуют обязательные колонки: "
            + ", ".join(sorted(missing_cols))
            + "."
        )
    elif net_sales_df.empty:
        errors.append("Нет данных net sales для пересчета прогноза.")

    return errors
