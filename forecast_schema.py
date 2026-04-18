import pandas as pd


# Storage column names (database) - individual weekly intervals
INTERNAL_FORECAST_COLUMNS = [
    "sku",
    "whole_period_sales",
    "sales_interval_m4w",  # days -27 to -21 (7 days)
    "sales_interval_m3w",  # days -20 to -14 (7 days)
    "sales_interval_m2w",  # days -13 to -7 (7 days)
    "sales_interval_m1w",  # days -6 to 0 (7 days)
    "trend_coef",
    "forecast_interval_p1w",  # +1 to +7 days
    "forecast_interval_p2w",  # +8 to +14 days
    "forecast_interval_p3w",  # +15 to +21 days
    "forecast_interval_p4w",  # +22 to +28 days
    "whole_period_forecast",
]

# Mapping from storage names to display names
STORAGE_TO_DISPLAY = {
    "sales_interval_m4w": "sales_-4w",
    "sales_interval_m3w": "sales_-3w",
    "sales_interval_m2w": "sales_-2w",
    "sales_interval_m1w": "sales_-1w",
    "forecast_interval_p1w": "forecast_+1w",
    "forecast_interval_p2w": "forecast_+2w",
    "forecast_interval_p3w": "forecast_+3w",
    "forecast_interval_p4w": "forecast_+4w",
}

# Display column names (UI) - with display-friendly names
DISPLAY_FORECAST_COLUMNS = [
    "sku",
    "whole_period_sales",
    "sales_-4w",
    "sales_-3w",
    "sales_-2w",
    "sales_-1w",
    "trend_coef",
    "forecast_+1w",
    "forecast_+2w",
    "forecast_+3w",
    "forecast_+4w",
    "whole_period_forecast",
]

DISPLAY_FORECAST_INT_COLUMNS = [
    "whole_period_sales",
    "sales_-4w",
    "sales_-3w",
    "sales_-2w",
    "sales_-1w",
    "forecast_+1w",
    "forecast_+2w",
    "forecast_+3w",
    "forecast_+4w",
    "whole_period_forecast",
]


def build_forecast_display_df(forecast_df: pd.DataFrame) -> pd.DataFrame:
    """
    Builds a UI-ready forecast table by renaming storage columns to display names.
    Database already stores individual non-overlapping intervals.
    """
    display_df = forecast_df.copy()
    if 'last_updated' in display_df.columns:
        display_df = display_df.drop(columns=['last_updated'])

    # Rename storage column names to display names
    rename_map = {k: v for k, v in STORAGE_TO_DISPLAY.items() if k in display_df.columns}
    display_df = display_df.rename(columns=rename_map)

    display_df = display_df.reindex(columns=DISPLAY_FORECAST_COLUMNS)

    # Cast numeric columns to integers
    for col in DISPLAY_FORECAST_INT_COLUMNS:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors='coerce').fillna(0).astype(int)

    return display_df
