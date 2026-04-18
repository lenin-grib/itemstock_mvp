"""
Orchestration logic for the Suppliers tab (supplier edit, change detection, save).
No Streamlit UI calls beyond parameter passing. Pure business orchestration.
"""
from supplier_service import get_suppliers, update_supplier_info
from suppliers_view_service import (
    build_suppliers_display_df,
    detect_supplier_changes,
    normalize_suppliers_for_save,
)


def load_suppliers_data():
    """
    Load supplier data and convert to display format.
    Returns tuple: (suppliers_df, display_df)
    """
    import pandas as pd
    
    try:
        suppliers_df = get_suppliers()
        if not suppliers_df.empty:
            display_df = build_suppliers_display_df(suppliers_df)
            return suppliers_df, display_df
    except Exception:
        pass
    
    return pd.DataFrame(), pd.DataFrame()


def process_supplier_changes(original_display_df, edited_display_df):
    """
    Detect changes and persist supplier updates.
    Returns tuple: (has_changes, detected_changes, error_msg)
    """
    if original_display_df is None or edited_display_df is None:
        return False, {}, None
    
    if original_display_df.empty or edited_display_df.empty:
        return False, {}, None
    
    changes = detect_supplier_changes(original_display_df, edited_display_df)
    
    if not changes:
        return False, {}, None
    
    try:
        normalized = normalize_suppliers_for_save(edited_display_df)
        for _, row in normalized.iterrows():
            update_supplier_info(
                row['name'],
                row['delivery_cost'],
                row['delivery_time'],
                row['min_order']
            )
        return True, changes, None
    except Exception as e:
        return False, {}, f"Ошибка при сохранении поставщиков: {str(e)}"
