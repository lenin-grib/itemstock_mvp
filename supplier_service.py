import pandas as pd
from db_utils import get_session
from database import Supplier, SupplierItem, ApproximatePrice
from utils import normalize


def save_supplier_file(file):
    """
    Parse and save supplier data from Excel file.
    Updates suppliers and their items, then updates approximate prices.
    """
    xls = pd.read_excel(file, sheet_name=None)
    if not xls:
        raise ValueError("Файл поставщиков пуст")

    first_sheet = next(iter(xls.values()))
    meta_df = first_sheet.copy()
    meta_df.columns = [str(col).strip().lower() for col in meta_df.columns]
    required_cols = ['поставщик', 'контакт', 'срок доставки', 'цена доставки', 'минимальный заказ']
    for col in required_cols:
        if col not in meta_df.columns:
            raise ValueError(f"В файле поставщиков не найдена колонка: {col}")

    session = get_session()
    try:
        suppliers = {}
        for _, row in meta_df.iterrows():
            name = str(row.get('поставщик', '')).strip()
            if not name:
                continue
            contact = str(row.get('контакт', '')).strip()
            delivery_time = str(row.get('срок доставки', '')).strip()
            delivery_cost = row.get('цена доставки', 0) or 0
            min_order = row.get('минимальный заказ', 0) or 0

            supplier = session.query(Supplier).filter_by(name=name).first()
            if not supplier:
                supplier = Supplier(
                    name=name,
                    contact=contact,
                    delivery_cost=float(delivery_cost),
                    delivery_time=delivery_time,
                    min_order=float(min_order)
                )
                session.add(supplier)
                session.flush()
            else:
                supplier.contact = contact
                supplier.delivery_cost = float(delivery_cost)
                supplier.delivery_time = delivery_time
                supplier.min_order = float(min_order)

            suppliers[name] = supplier

        session.commit()

        # Clear supplier items for all suppliers in this file
        for supplier in suppliers.values():
            session.query(SupplierItem).filter_by(supplier_id=supplier.id).delete()
        session.commit()

        # Parse price lists from subsequent sheets
        for sheet_name, sheet in list(xls.items())[1:]:
            if sheet.empty:
                continue
            sheet_name_lower = sheet_name.strip().lower()
            supplier = None
            for name, sup in suppliers.items():
                normalized_name = normalize(name)
                if normalized_name == sheet_name_lower or normalized_name in sheet_name_lower or sheet_name_lower in normalized_name:
                    supplier = sup
                    break
            if supplier is None:
                continue

            items_df = sheet.copy()
            items_df.columns = [str(col).strip().lower() for col in items_df.columns]
            if 'товар' not in items_df.columns or 'цена' not in items_df.columns:
                continue

            for _, item_row in items_df.iterrows():
                sku = str(item_row.get('товар', '')).strip()
                if not sku:
                    continue
                price = item_row.get('цена', 0) or 0
                packaging = str(item_row.get('упаковка', '')).strip()

                supplier_item = SupplierItem(
                    supplier_id=supplier.id,
                    sku=sku,
                    price=float(price),
                    packaging=packaging
                )
                session.add(supplier_item)

        session.commit()

        # Update approximate prices from supplier items
        session.query(ApproximatePrice).delete()
        session.commit()

        price_map = {}
        for sku, price in session.query(SupplierItem.sku, SupplierItem.price).all():
            if sku not in price_map or price < price_map[sku]:
                price_map[sku] = price

        for sku, price in price_map.items():
            approx = ApproximatePrice(sku=sku, price=price)
            session.add(approx)

        session.commit()

    finally:
        session.close()


def get_suppliers():
    """
    Get all suppliers with item counts.
    Returns DataFrame with supplier info.
    """
    session = get_session()
    try:
        suppliers = session.query(Supplier).all()
        data = []
        for supplier in suppliers:
            item_count = session.query(SupplierItem).filter_by(supplier_id=supplier.id).count()
            data.append({
                'name': supplier.name,
                'delivery_cost': supplier.delivery_cost,
                'delivery_time': supplier.delivery_time,
                'min_order': supplier.min_order,
                'contact': supplier.contact,
                'item_count': item_count
            })
        return pd.DataFrame(data) if data else pd.DataFrame()
    finally:
        session.close()


def update_supplier_info(name, delivery_cost, delivery_time, min_order):
    """
    Update supplier delivery information.
    """
    session = get_session()
    try:
        supplier = session.query(Supplier).filter_by(name=name).first()
        if supplier:
            supplier.delivery_cost = float(delivery_cost or 0)
            supplier.delivery_time = str(delivery_time or '')
            supplier.min_order = float(min_order or 0)
            session.commit()
    finally:
        session.close()


def get_supplier_items(supplier_name=None):
    """
    Get supplier items, optionally filtered by supplier name.
    Returns DataFrame with item details.
    """
    session = get_session()
    try:
        query = session.query(SupplierItem, Supplier.name).join(Supplier)
        if supplier_name:
            query = query.filter(Supplier.name == supplier_name)
        data = []
        for item, supplier_name in query.all():
            data.append({
                'supplier_name': supplier_name,
                'sku': item.sku,
                'price': item.price,
                'packaging': item.packaging
            })
        return pd.DataFrame(data) if data else pd.DataFrame()
    finally:
        session.close()