"""
Orchestration logic for the Parameters tab (parameter update, validation, database reset).
No Streamlit UI calls beyond parameter passing. Pure business orchestration.
"""
from db_utils import update_parameters, reset_database_data, get_parameters
from cache_service import invalidate_forecast_cache, invalidate_ideal_stock_cache
from ui_helpers import parse_trend_weeks


def load_parameters():
    """Load current parameters from database."""
    return get_parameters()


def normalize_trend_period(params_dict):
    """
    Normalize trend period from old/new format.
    Returns trend_weeks value.
    """
    trend_weeks_raw = params_dict.get('trend_period_weeks', int(params_dict.get('trend_period_months', 2) * 4))
    return trend_weeks_raw


def validate_and_save_parameters(new_quote, new_min_stock, new_trend_period):
    """
    Validate parameter values and update database.
    Returns tuple: (is_valid, error_msg, should_rerun)
    """
    validated_trend_weeks, trend_error = parse_trend_weeks(new_trend_period)
    if trend_error:
        return False, trend_error, False
    
    try:
        update_parameters({
            'quote_multiplicator': new_quote,
            'min_items_in_stock': new_min_stock,
            'trend_period_weeks': validated_trend_weeks,
        })
        
        invalidate_forecast_cache()
        invalidate_ideal_stock_cache()
        
        return True, None, True
    except Exception as e:
        return False, f"Не удалось сохранить параметры: {e}", False


def process_database_reset():
    """
    Execute full database reset.
    Returns tuple: (success, error_msg)
    """
    try:
        reset_database_data()
        return True, None
    except Exception as e:
        return False, f"Не удалось сбросить БД: {e}"
