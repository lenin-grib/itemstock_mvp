from db_utils import get_session, CachedForecast, CachedIdealStock


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


def get_cached_forecasts():
    """
    Get cached forecast data.
    Returns DataFrame with forecast data.
    """
    session = get_session()
    try:
        forecasts = session.query(CachedForecast).all()
        data = []
        for f in forecasts:
            data.append({
                'sku': f.sku,
                'whole_period_sales': f.whole_period_sales,
                'sales_last_week': f.sales_last_week,
                'sales_last_2w': f.sales_last_2w,
                'sales_last_3w': f.sales_last_3w,
                'sales_last_month': f.sales_last_month,
                'trend_coef': f.trend_coef,
                'forecast_next_week': f.forecast_next_week,
                'forecast_2w': f.forecast_2w,
                'forecast_3w': f.forecast_3w,
                'forecast_next_month': f.forecast_next_month,
                'last_updated': f.last_updated,
            })
        import pandas as pd
        if data:
            return pd.DataFrame(data)
        return pd.DataFrame(columns=[
            'sku', 'whole_period_sales',
            'sales_last_week', 'sales_last_2w', 'sales_last_3w', 'sales_last_month',
            'trend_coef',
            'forecast_next_week', 'forecast_2w', 'forecast_3w', 'forecast_next_month',
            'last_updated',
        ])
    finally:
        session.close()


def save_forecast_cache(df):
    """
    Save forecast data to cache.
    """
    session = get_session()
    try:
        session.query(CachedForecast).delete()
        session.commit()

        for _, row in df.iterrows():
            cached = CachedForecast(
                sku=row['sku'],
                whole_period_sales=row.get('whole_period_sales'),
                sales_last_week=row.get('sales_last_week'),
                sales_last_2w=row.get('sales_last_2w'),
                sales_last_3w=row.get('sales_last_3w'),
                sales_last_month=row.get('sales_last_month'),
                trend_coef=row.get('trend_coef'),
                forecast_next_week=int(row.get('forecast_next_week', 0) or 0),
                forecast_2w=int(row.get('forecast_2w', 0) or 0),
                forecast_3w=int(row.get('forecast_3w', 0) or 0),
                forecast_next_month=int(row.get('forecast_next_month', 0) or 0),
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
        import pandas as pd
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
            )
            session.add(cached)
        session.commit()
    finally:
        session.close()