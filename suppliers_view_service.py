import pandas as pd


SUPPLIER_DISPLAY_COLUMNS = [
    'name',
    'delivery_cost',
    'delivery_time',
    'min_order',
]

SUPPLIER_DISPLAY_RENAME_MAP = {
    'name': 'Название',
    'delivery_cost': 'Стоимость доставки',
    'delivery_time': 'Срок доставки',
    'min_order': 'Минимальный заказ',
}

SUPPLIER_STORAGE_RENAME_MAP = {v: k for k, v in SUPPLIER_DISPLAY_RENAME_MAP.items()}


def build_suppliers_display_df(suppliers_df):
    """Builds supplier table for Streamlit editor."""
    if suppliers_df is None or suppliers_df.empty:
        return pd.DataFrame(columns=list(SUPPLIER_DISPLAY_RENAME_MAP.values()))

    display_df = suppliers_df[SUPPLIER_DISPLAY_COLUMNS].rename(columns=SUPPLIER_DISPLAY_RENAME_MAP)
    return display_df


def detect_supplier_changes(original_display_df, edited_display_df):
    """Returns mapping: supplier_name -> list of changed display columns."""
    if original_display_df is None or edited_display_df is None:
        return {}

    if original_display_df.empty or edited_display_df.empty:
        return {}

    original_values = original_display_df.set_index('Название')
    edited_values = edited_display_df.set_index('Название')

    changes = {}
    tracked_columns = ['Стоимость доставки', 'Срок доставки', 'Минимальный заказ']
    for name in original_values.index:
        if name not in edited_values.index:
            continue

        original_row = original_values.loc[name]
        edited_row = edited_values.loc[name]
        changed_columns = [col for col in tracked_columns if original_row[col] != edited_row[col]]
        if changed_columns:
            changes[name] = changed_columns

    return changes


def normalize_suppliers_for_save(edited_display_df):
    """Converts edited supplier dataframe from display names to storage names."""
    if edited_display_df is None or edited_display_df.empty:
        return pd.DataFrame(columns=SUPPLIER_DISPLAY_COLUMNS)

    return edited_display_df.rename(columns=SUPPLIER_STORAGE_RENAME_MAP)
