"""
Orchestration logic for the Sales tab (logs, spoils upload, forecast display).
No Streamlit UI calls beyond parameter passing. Pure business orchestration.
"""
from db_utils import get_uploaded_files, get_net_sales_data
from parser import parse_and_save_file, parse_and_save_spoils_file
from forecast import get_forecasts
from cache_service import invalidate_forecast_cache, invalidate_ideal_stock_cache
from db_utils import get_current_stock
from ideal_stock import get_ideal_stock
from sales_view_service import build_sales_view_model, get_default_popular_threshold
from ui_helpers import (
    normalize_uploaded_file_row,
    get_uploaded_file_signature,
    validate_forecast_recalc_inputs,
    parse_trend_weeks,
)


def get_uploaded_file_metadata():
    """
    Load and normalize all uploaded files from database.
    Returns tuple: (normalized_files, has_logs, has_spoils, has_price, latest_logs_date)
    """
    all_files = get_uploaded_files()
    normalized = [normalize_uploaded_file_row(r) for r in all_files]
    
    log_files = [f for f in normalized if str(f[2] or 'logs') == 'logs']
    has_logs = len(log_files) > 0
    has_spoils = any(str(f[2] or 'logs') == 'spoils' for f in normalized)
    has_price = any(str(f[2] or 'logs') == 'price' for f in normalized)
    
    latest_date = max(
        (f[5] for f in log_files if f[5] is not None),
        default=None,
    )
    
    return normalized, has_logs, has_spoils, has_price, latest_date


def process_logs_upload(logs_file, processed_signatures):
    """
    Process uploaded logs file(s).
    Returns tuple: (updated_signatures, should_rerun, error_msg)
    """
    if not logs_file:
        return processed_signatures, False, None
    
    updated_sigs = processed_signatures.copy()
    files = logs_file if isinstance(logs_file, list) else [logs_file]
    
    logs_changed = False
    for file in files:
        sig = get_uploaded_file_signature(file)
        if sig in processed_signatures:
            continue
        
        try:
            parse_and_save_file(file)
            invalidate_forecast_cache()
            invalidate_ideal_stock_cache()
            updated_sigs.add(sig)
            logs_changed = True
        except Exception as e:
            return processed_signatures, False, f"Ошибка при обработке файла {file.name}: {str(e)}"
    
    return updated_sigs, logs_changed, None


def process_spoils_upload(spoils_file, processed_signature):
    """
    Process uploaded spoils file.
    Returns tuple: (new_signature, should_rerun, error_msg)
    """
    if spoils_file is None:
        return processed_signature, False, None
    
    sig = get_uploaded_file_signature(spoils_file)
    if sig == processed_signature:
        return processed_signature, False, None
    
    try:
        parse_and_save_spoils_file(spoils_file)
        invalidate_forecast_cache()
        invalidate_ideal_stock_cache()
        return sig, True, None
    except Exception as e:
        return processed_signature, False, f"Ошибка при обработке файла списаний {spoils_file.name}: {str(e)}"


def load_forecast_and_stock(trend_weeks):
    """
    Load forecast and current stock data.
    Returns tuple: (forecast_df, stock_df) or (empty_df, empty_df) on error
    """
    import pandas as pd
    from forecast_schema import INTERNAL_FORECAST_COLUMNS
    
    _FORECAST_COLS = INTERNAL_FORECAST_COLUMNS
    _STOCK_COLS = ['sku', 'current_stock']
    
    try:
        forecast_df = get_forecasts(trend_period_weeks=trend_weeks)
    except Exception:
        forecast_df = pd.DataFrame(columns=_FORECAST_COLS)
    
    try:
        stock_df = get_current_stock()
    except Exception:
        stock_df = pd.DataFrame(columns=_STOCK_COLS)
    
    return forecast_df, stock_df


def prepare_sales_view_data(forecast_df, stock_df, popular_threshold):
    """
    Build sales view model with popular and no-demand products.
    Returns sales_view_model.
    """
    return build_sales_view_model(
        forecast_df=forecast_df,
        stock_df=stock_df,
        popular_threshold=popular_threshold,
    )


def validate_and_refresh_forecast(trend_weeks, latest_logs_date):
    """
    Validate inputs and refresh forecast.
    Returns tuple: (recalc_errors, should_rerun)
    """
    errors = validate_forecast_recalc_inputs(trend_weeks, latest_logs_date)
    if errors:
        return errors, False
    
    invalidate_forecast_cache()
    return [], True
