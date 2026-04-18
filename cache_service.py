from datetime import datetime

from sqlalchemy import func

from db_utils import get_session, CachedForecast, CachedIdealStock
from database import UploadedFile
from forecast_schema import INTERNAL_FORECAST_COLUMNS
import pandas as pd


def _latest_upload_date(session, file_types):
    return session.query(func.max(UploadedFile.upload_date)).filter(UploadedFile.file_type.in_(file_types)).scalar()


def _is_cache_stale(cached_last_updated, source_last_updated):
    if cached_last_updated is None:
        return True
    if source_last_updated is None:
        return False
    return cached_last_updated < source_last_updated


def invalidate_forecast_cache():
    """
    Clear all cached forecast data.
    """
    session = get_session()
    try:
        session.query(CachedForecast).delete()
        session.commit()
    finally:
        session.close()


def invalidate_ideal_stock_cache():
    """
    Clear all cached ideal stock data.
    """
    session = get_session()
    try:
        session.query(CachedIdealStock).delete()
        session.commit()
    finally:
        session.close()


def get_cached_forecasts(trend_period_weeks=None):
    """
    Get cached forecast data.
    Returns DataFrame with forecast data.
    """
    session = get_session()
    try:
        query = session.query(CachedForecast)
        if trend_period_weeks is not None:
            query = query.filter(CachedForecast.trend_period_weeks == int(trend_period_weeks))
        forecasts = query.all()
        if not forecasts:
            return pd.DataFrame(columns=INTERNAL_FORECAST_COLUMNS + ['last_updated'])

        cache_last_updated = max((f.last_updated for f in forecasts if f.last_updated is not None), default=None)
        source_last_updated = _latest_upload_date(session, ['logs', 'spoils'])
        if _is_cache_stale(cache_last_updated, source_last_updated):
            return pd.DataFrame(columns=INTERNAL_FORECAST_COLUMNS + ['last_updated'])

        data = []
        for f in forecasts:
            data.append({
                'sku': f.sku,
                'trend_period_weeks': f.trend_period_weeks,
                'whole_period_sales': f.whole_period_sales,
                'sales_interval_m4w': f.sales_interval_m4w,
                'sales_interval_m3w': f.sales_interval_m3w,
                'sales_interval_m2w': f.sales_interval_m2w,
                'sales_interval_m1w': f.sales_interval_m1w,
                'trend_coef': f.trend_coef,
                'forecast_interval_p1w': f.forecast_interval_p1w,
                'forecast_interval_p2w': f.forecast_interval_p2w,
                'forecast_interval_p3w': f.forecast_interval_p3w,
                'forecast_interval_p4w': f.forecast_interval_p4w,
                'whole_period_forecast': f.whole_period_forecast,
                'last_updated': f.last_updated,
            })
        if data:
            return pd.DataFrame(data)
        return pd.DataFrame(columns=['trend_period_weeks'] + INTERNAL_FORECAST_COLUMNS + ['last_updated'])
    finally:
        session.close()


def save_forecast_cache(df, trend_period_weeks=None):
    """
    Save forecast data to cache.
    """
    session = get_session()
    try:
        session.query(CachedForecast).delete()
        session.commit()

        now = datetime.now()
        trend_weeks_value = None if trend_period_weeks is None else int(trend_period_weeks)
        for _, row in df.iterrows():
            cached = CachedForecast(
                sku=row['sku'],
            trend_period_weeks=trend_weeks_value,
                whole_period_sales=row.get('whole_period_sales'),
                sales_interval_m4w=row.get('sales_interval_m4w'),
                sales_interval_m3w=row.get('sales_interval_m3w'),
                sales_interval_m2w=row.get('sales_interval_m2w'),
                sales_interval_m1w=row.get('sales_interval_m1w'),
                trend_coef=row.get('trend_coef'),
                forecast_interval_p1w=int(row.get('forecast_interval_p1w', 0) or 0),
                forecast_interval_p2w=int(row.get('forecast_interval_p2w', 0) or 0),
                forecast_interval_p3w=int(row.get('forecast_interval_p3w', 0) or 0),
                forecast_interval_p4w=int(row.get('forecast_interval_p4w', 0) or 0),
                whole_period_forecast=int(row.get('whole_period_forecast', 0) or 0),
                last_updated=now,
            )
            session.add(cached)
        session.commit()
    finally:
        session.close()


def get_cached_ideal_stock():
    """
    Get cached ideal stock data.
    Returns DataFrame with ideal stock calculations.
    """
    session = get_session()
    try:
        stocks = session.query(CachedIdealStock).all()
        if not stocks:
            return pd.DataFrame(columns=[
                'sku', 'current_stock',
                'ideal_stock', 'ideal_stock_2w', 'ideal_stock_3w', 'monthly_ideal_stock',
                'to_order_week', 'to_order_2w', 'to_order_3w', 'to_order_month',
                'last_updated',
            ])

        cache_last_updated = max((s.last_updated for s in stocks if s.last_updated is not None), default=None)
        source_last_updated = _latest_upload_date(session, ['logs', 'spoils'])
        latest_forecast_cache = session.query(func.max(CachedForecast.last_updated)).scalar()
        freshest_dependency = max([d for d in (source_last_updated, latest_forecast_cache) if d is not None], default=None)
        if _is_cache_stale(cache_last_updated, freshest_dependency):
            return pd.DataFrame(columns=[
                'sku', 'current_stock',
                'ideal_stock', 'ideal_stock_2w', 'ideal_stock_3w', 'monthly_ideal_stock',
                'to_order_week', 'to_order_2w', 'to_order_3w', 'to_order_month',
                'last_updated',
            ])

        data = []
        for s in stocks:
            data.append({
                'sku': s.sku,
                'current_stock': s.current_stock,
                'ideal_stock': s.ideal_stock,
                'ideal_stock_2w': s.ideal_stock_2w,
                'ideal_stock_3w': s.ideal_stock_3w,
                'monthly_ideal_stock': s.monthly_ideal_stock,
                'to_order_week': s.to_order_week,
                'to_order_2w': s.to_order_2w,
                'to_order_3w': s.to_order_3w,
                'to_order_month': s.to_order_month,
                'last_updated': s.last_updated,
            })
        return pd.DataFrame(data) if data else pd.DataFrame(columns=[
            'sku', 'current_stock',
            'ideal_stock', 'ideal_stock_2w', 'ideal_stock_3w', 'monthly_ideal_stock',
            'to_order_week', 'to_order_2w', 'to_order_3w', 'to_order_month',
            'last_updated',
        ])
    finally:
        session.close()


def save_ideal_stock_cache(df):
    """
    Save ideal stock data to cache.
    """
    session = get_session()
    try:
        session.query(CachedIdealStock).delete()
        session.commit()

        now = datetime.now()
        for _, row in df.iterrows():
            cached = CachedIdealStock(
                sku=row['sku'],
                current_stock=int(row.get('current_stock', 0) or 0),
                ideal_stock=int(row.get('ideal_stock', 0) or 0),
                ideal_stock_2w=int(row.get('ideal_stock_2w', 0) or 0),
                ideal_stock_3w=int(row.get('ideal_stock_3w', 0) or 0),
                monthly_ideal_stock=int(row.get('monthly_ideal_stock', 0) or 0),
                to_order_week=int(row.get('to_order_week', 0) or 0),
                to_order_2w=int(row.get('to_order_2w', 0) or 0),
                to_order_3w=int(row.get('to_order_3w', 0) or 0),
                to_order_month=int(row.get('to_order_month', 0) or 0),
                last_updated=now,
            )
            session.add(cached)
        session.commit()
    finally:
        session.close()