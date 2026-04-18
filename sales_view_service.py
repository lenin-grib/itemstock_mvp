from dataclasses import dataclass

import pandas as pd

from db_utils import get_all_skus


@dataclass
class SalesViewModel:
    popular_df: pd.DataFrame
    no_demand_df: pd.DataFrame


def get_default_popular_threshold(period_weeks):
    return max(1, int(35 * (float(period_weeks) / 4)))


def build_sales_view_model(forecast_df, stock_df, popular_threshold):
    """Builds UI-ready popular and no-demand datasets for sales tab."""
    sales_view = forecast_df[['sku', 'whole_period_sales', 'whole_period_forecast']].copy()
    sales_view['net_sales_period'] = pd.to_numeric(sales_view['whole_period_sales'], errors='coerce').fillna(0)

    stock_subset = stock_df[['sku', 'current_stock']].copy() if 'sku' in stock_df.columns else pd.DataFrame(columns=['sku', 'current_stock'])
    sales_view = sales_view.merge(stock_subset, on='sku', how='left')
    sales_view['current_stock'] = sales_view['current_stock'].fillna(0)

    popular_df = sales_view.loc[
        sales_view['net_sales_period'] > float(popular_threshold),
        ['sku', 'net_sales_period', 'current_stock', 'whole_period_forecast']
    ].sort_values('net_sales_period', ascending=False)

    popular_df = popular_df.rename(columns={
        'sku': 'Товар',
        'net_sales_period': 'Продажи за период',
        'current_stock': 'Осталось на складе',
        'whole_period_forecast': 'Прогноз на период',
    })

    no_demand_df = sales_view.loc[sales_view['net_sales_period'] == 0, ['sku']].copy()

    all_skus = get_all_skus()
    existing_no_demand = set(no_demand_df['sku'])
    existing_sales = set(sales_view['sku'])
    additional_no_demand = [
        {'sku': sku}
        for sku in all_skus
        if sku not in existing_sales and sku not in existing_no_demand
    ]
    if additional_no_demand:
        no_demand_df = pd.concat([no_demand_df, pd.DataFrame(additional_no_demand)], ignore_index=True)

    return SalesViewModel(
        popular_df=popular_df,
        no_demand_df=no_demand_df,
    )
