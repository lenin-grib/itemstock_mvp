import re

import pandas as pd

from db_utils import get_session
from database import PriceListItem, Product, Supplier


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


def build_recommended_orders(order_df):
    """
    Build grouped supplier orders from monthly demand (to_order_month) and price list.

    Returns:
      orders: list[dict]
      missing_supplier_skus: list[str]
      below_min_order_warnings: list[dict]
    """
    if order_df is None or order_df.empty:
        return [], [], []

    required = order_df[['sku', 'to_order_month']].copy()
    required['to_order_month'] = pd.to_numeric(required['to_order_month'], errors='coerce').fillna(0)
    required = required[required['to_order_month'] > 0].copy()
    if required.empty:
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
            offer = {
                'supplier_id': row[1],
                'supplier_name': row[2],
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
            required_qty = float(row['to_order_month'])
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

        orders = sorted(orders, key=lambda x: x['total_cost'], reverse=True)

        below_min_order_warnings = []
        for order in orders:
            if order['min_order'] > 0 and order['subtotal_without_delivery'] < order['min_order']:
                below_min_order_warnings.append({
                    'supplier_name': order['supplier_name'],
                    'subtotal_without_delivery': order['subtotal_without_delivery'],
                    'min_order': order['min_order'],
                })

        return orders, missing_supplier_skus, below_min_order_warnings
    finally:
        session.close()
