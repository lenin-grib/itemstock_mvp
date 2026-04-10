import pandas as pd
import re
from datetime import datetime


def load_multiple_files(uploaded_files):
    """
    Принимает список файлов из Streamlit file_uploader
    Возвращает единый DataFrame
    """
    all_data = []

    for file in uploaded_files:
        df = parse_single_file(file)
        all_data.append(df)

    if not all_data:
        return pd.DataFrame()

    return pd.concat(all_data, ignore_index=True)



def parse_single_file(file):
    """
    Парсит один Excel-файл с 3-строчным хедером
    """

    # читаем multi-header (2 строки после title)
    df = pd.read_excel(file, header=[1, 2])

    # сплющиваем колонки
    df.columns = [flatten_column(col) for col in df.columns]

    # теперь можно спокойно работать
    df = df.dropna(subset=["Наименование"])

    # базовые колонки
    base_cols = [
        "Наименование",
        "Остаток на начало периода",
        "Остаток на конец периода"
    ]

    date_cols = [col for col in df.columns if is_date_column(col)]

    df = df[base_cols + date_cols]

    records = []

    for _, row in df.iterrows():
        sku = row["Наименование"]
        opening_balance = row["Остаток на начало периода"]

        for col in date_cols:
            date_str, is_outbound = parse_column_name(col)

            try:
                date = datetime.strptime(date_str, "%d.%m.%Y")
            except:
                continue

            value = row[col]
            if pd.isna(value):
                value = 0

            records.append({
                "sku": sku,
                "date": date,
                "inbound": 0 if is_outbound else value,
                "outbound": value if is_outbound else 0,
                "weekday": date.strftime("%A"),
                "weekday_num": date.weekday(),
                "opening_balance": opening_balance,
                "source_file": getattr(file, "name", "unknown")
            })

    result = pd.DataFrame(records)

    result = result.groupby(
        ["sku", "date", "weekday", "weekday_num", "opening_balance", "source_file"],
        as_index=False
    ).agg({
        "inbound": "sum",
        "outbound": "sum"
    })

    result = compute_inventory_balance(result)

    return result


# -----------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# -----------------------

def flatten_column(col):
    top, bottom = col

    if isinstance(top, str) and re.match(r"\d{2}\.\d{2}\.\d{4}", top):
        if "Расх" in str(bottom):
            return f"{top}.1"  # расход
        elif "Прих" in str(bottom):
            return f"{top}"   # приход

    return str(bottom).strip()

def is_date_column(col_name):
    """
    Проверяет, является ли колонка датой или датой расхода
    """
    return bool(re.match(r"\d{2}\.\d{2}\.\d{4}(\.1)?$", str(col_name)))


def parse_column_name(col_name):
    """
    Возвращает:
    (date_str, is_outbound)
    """
    col_name = str(col_name)

    if col_name.endswith(".1"):
        return col_name[:-2], True  # расход

    return col_name, False  # приход


def compute_inventory_balance(df):
    """Добавляет колонку остатка на складе по накоплению прихода и расхода."""
    if df.empty:
        return df

    df = df.sort_values(["sku", "source_file", "date"])
    df["cumulative_inbound"] = df.groupby(["sku", "source_file"])["inbound"].cumsum()
    df["cumulative_outbound"] = df.groupby(["sku", "source_file"])["outbound"].cumsum()
    df["остаток на складе"] = (
        df["opening_balance"]
        - df["cumulative_outbound"]
        + df["cumulative_inbound"]
    )

    return df.drop(columns=["cumulative_inbound", "cumulative_outbound"])
