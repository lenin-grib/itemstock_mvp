"""
Orchestration logic for the Orders tab (price upload, ideal stock, recommended orders).
No Streamlit UI calls beyond parameter passing. Pure business orchestration.
"""
from db_utils import get_current_stock
from ideal_stock import get_ideal_stock
from order_service import ORDER_PERIOD_TO_ORDER_COLUMN
from orders_view_service import build_orders_view_model
from parser import parse_and_save_price_list_file
from cache_service import invalidate_ideal_stock_cache
from ui_helpers import get_uploaded_file_signature


def process_price_list_upload(price_file, processed_signature):
    """
    Process uploaded price list file.
    Returns tuple: (new_signature, should_rerun, error_msg)
    """
    if price_file is None:
        return processed_signature, False, None
    
    sig = get_uploaded_file_signature(price_file)
    if sig == processed_signature:
        return processed_signature, False, None
    
    try:
        parse_and_save_price_list_file(price_file)
        return sig, True, None
    except Exception as e:
        return processed_signature, False, f"Ошибка при обработке прайс-листа {price_file.name}: {str(e)}"


def load_ideal_stock_data():
    """
    Load ideal stock and current stock data.
    Returns tuple: (ideal_stock_df, stock_df)
    """
    import pandas as pd
    
    try:
        ideal_stock_df = get_ideal_stock()
    except Exception:
        ideal_stock_df = pd.DataFrame(columns=[
            'sku', 'current_stock',
            'ideal_stock', 'ideal_stock_2w', 'ideal_stock_3w', 'monthly_ideal_stock',
            'to_order_week', 'to_order_2w', 'to_order_3w', 'to_order_month',
        ])
    
    try:
        stock_df = get_current_stock()
    except Exception:
        stock_df = pd.DataFrame(columns=['sku', 'current_stock'])
    
    return ideal_stock_df, stock_df


def prepare_order_display_data(ideal_stock_df, period_weeks):
    """
    Filter and prepare order data for display.
    Returns tuple: (order_df, active_to_order_col, active_ideal_col)
    """
    active_to_order = ORDER_PERIOD_TO_ORDER_COLUMN.get(int(period_weeks), 'to_order_month')
    active_ideal = {1: 'ideal_stock', 2: 'ideal_stock_2w', 3: 'ideal_stock_3w', 4: 'monthly_ideal_stock'}.get(period_weeks, 'monthly_ideal_stock')
    
    if active_to_order not in ideal_stock_df.columns:
        active_to_order = 'to_order_month'
    if active_ideal not in ideal_stock_df.columns:
        active_ideal = 'monthly_ideal_stock'
    
    order_df = ideal_stock_df.loc[ideal_stock_df[active_to_order] > 0]
    return order_df, active_to_order, active_ideal


def build_orders_view(order_df, period_weeks):
    """
    Build orders view model with recommended orders and warnings.
    Returns orders_view_model.
    """
    return build_orders_view_model(order_df, period_weeks=period_weeks)


def refresh_orders_cache():
    """Clear ideal stock cache to force recalculation."""
    invalidate_ideal_stock_cache()
