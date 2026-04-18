import re

import pandas as pd

from db_utils import get_session
from database import PriceListItem, Product, Supplier


ORDER_PERIOD_TO_ORDER_COLUMN = {
    1: 'to_order_week',
    2: 'to_order_2w',
    3: 'to_order_3w',
    4: 'to_order_month',
}


def _parse_packaging_units(packaging):
    if packaging is None:
        return 1

    text = str(packaging).strip()
    if not text:
        return 1

    match = re.search(r"\d+(?:[\.,]\d+)?", text)
    if not match:
        return 1

    value = float(match.group(0).replace(',', '.'))
    if value <= 0:
        return 1

    return max(1, int(round(value)))


def _round_to_next_pack_multiple(required_qty, pack_units):
    """Returns minimal multiple of pack_units strictly greater than required_qty."""
    if required_qty <= 0:
        return 0

    return (int(required_qty // pack_units) + 1) * pack_units


def _is_without_supplier_name(name):
    return str(name or '').strip().lower() == 'без поставщика'


def build_recommended_orders(order_df, period_weeks=4, include_zero_price_warnings=False):
    """
    Build grouped supplier orders for a given period (1-4 weeks).

    period_weeks: 1, 2, 3 or 4 – selects the matching to_order_Xw column.
        Returns by default:
            orders: list[dict]
            missing_supplier_skus: list[str]
            below_min_order_warnings: list[dict]

        If include_zero_price_warnings=True, returns an additional 4th element:
            zero_price_warnings: list[dict]
    """
    if order_df is None or order_df.empty:
                if include_zero_price_warnings:
                        return [], [], [], []
                return [], [], []

    to_order_col = ORDER_PERIOD_TO_ORDER_COLUMN.get(int(period_weeks), 'to_order_month')
    if to_order_col not in order_df.columns:
        to_order_col = 'to_order_month'

    required = order_df[['sku', to_order_col]].rename(columns={to_order_col: '_qty'}).copy()
    required['_qty'] = pd.to_numeric(required['_qty'], errors='coerce').fillna(0)
    required = required[required['_qty'] > 0].copy()
    if required.empty:
        if include_zero_price_warnings:
            return [], [], [], []
        return [], [], []

    skus = sorted(set(required['sku']))

    session = get_session()
    try:
        rows = (
            session.query(
                Product.sku,
                Supplier.id,
                Supplier.name,
                Supplier.delivery_cost,
                Supplier.delivery_time,
                Supplier.min_order,
                PriceListItem.purchase_price,
                PriceListItem.packaging,
            )
            .join(PriceListItem, PriceListItem.product_id == Product.id)
            .join(Supplier, Supplier.id == PriceListItem.supplier_id)
            .filter(Product.sku.in_(skus))
            .filter(PriceListItem.purchase_price.isnot(None))
            .all()
        )

        best_offer = {}
        for row in rows:
            sku = row[0]
            supplier_name = row[2]
            offer = {
                'supplier_id': row[1],
                'supplier_name': supplier_name,
                'is_without_supplier': _is_without_supplier_name(supplier_name),
                'delivery_cost': float(row[3] or 0),
                'delivery_time': row[4] or '',
                'min_order': float(row[5] or 0),
                'purchase_price': float(row[6]),
                'packaging': row[7],
            }

            if sku not in best_offer or offer['purchase_price'] < best_offer[sku]['purchase_price']:
                best_offer[sku] = offer

        missing_supplier_skus = sorted([sku for sku in skus if sku not in best_offer])

        grouped = {}
        for _, row in required.iterrows():
            sku = row['sku']
            if sku in missing_supplier_skus:
                continue

            offer = best_offer[sku]
            pack_units = _parse_packaging_units(offer['packaging'])
            required_qty = float(row['_qty'])
            order_qty = _round_to_next_pack_multiple(required_qty, pack_units)

            if order_qty <= 0:
                continue

            unit_price = offer['purchase_price']
            line_cost = unit_price * order_qty

            supplier_id = offer['supplier_id']
            if supplier_id not in grouped:
                grouped[supplier_id] = {
                    'supplier_id': supplier_id,
                    'supplier_name': offer['supplier_name'],
                    'is_without_supplier': offer['is_without_supplier'],
                    'delivery_cost': offer['delivery_cost'],
                    'delivery_time': offer['delivery_time'],
                    'min_order': offer['min_order'],
                    'subtotal_without_delivery': 0.0,
                    'total_cost': 0.0,
                    'items': [],
                }

            grouped[supplier_id]['items'].append({
                'Товар': sku,
                'Количество для заказа': int(order_qty),
                'Цена за единицу': float(unit_price),
                'Стоимость': float(line_cost),
            })
            grouped[supplier_id]['subtotal_without_delivery'] += float(line_cost)

        orders = []
        for order in grouped.values():
            order['subtotal_without_delivery'] = float(order['subtotal_without_delivery'])
            order['total_cost'] = float(order['subtotal_without_delivery'] + order['delivery_cost'])
            order['items'] = sorted(order['items'], key=lambda x: x['Товар'])
            orders.append(order)

        # Keep explicit "Без поставщика" group at the end while preserving cost order for others.
        orders = sorted(
            orders,
            key=lambda x: (1 if x.get('is_without_supplier') else 0, -x['total_cost'])
        )

        below_min_order_warnings = []
        zero_price_warnings = []
        for order in orders:
            if order['min_order'] > 0 and order['subtotal_without_delivery'] < order['min_order']:
                below_min_order_warnings.append({
                    'supplier_name': order['supplier_name'],
                    'subtotal_without_delivery': order['subtotal_without_delivery'],
                    'min_order': order['min_order'],
                })
            zero_price_items = [i['Товар'] for i in order.get('items', []) if float(i.get('Цена за единицу', 0) or 0) == 0]
            if zero_price_items:
                zero_price_warnings.append({
                    'supplier_name': order['supplier_name'],
                    'items': sorted(set(zero_price_items)),
                })

        if include_zero_price_warnings:
            return orders, missing_supplier_skus, below_min_order_warnings, zero_price_warnings
        return orders, missing_supplier_skus, below_min_order_warnings
    finally:
        session.close()
