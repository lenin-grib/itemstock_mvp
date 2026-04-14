from datetime import datetime

import pandas as pd

from db_utils import get_session
from database import (
    ApproximatePrice,
    PriceListItem,
    Product,
    Supplier,
    SupplierItem,
    UploadedFile,
)


def _upsert_uploaded_file(session, filename, file_type, date_from=None, date_to=None):
    existing = session.query(UploadedFile).filter_by(filename=filename).first()
    if existing:
        existing.file_type = file_type
        existing.upload_date = datetime.now()
        existing.date_from = date_from
        existing.date_to = date_to
        return existing

    uploaded = UploadedFile(
        filename=filename,
        file_type=file_type,
        upload_date=datetime.now(),
        date_from=date_from,
        date_to=date_to,
    )
    session.add(uploaded)
    session.flush()
    return uploaded


def _is_without_supplier_name(name):
    return str(name or '').strip().lower() == 'без поставщика'


def save_supplier_file(file):
    """
    Parse and save suppliers from a single-sheet file with supplier metadata only.
    Required columns:
      поставщик, контакт, срок доставки, цена доставки, минимальный заказ
    Also stores file record in uploaded_files with upload date as date range.
    """
    df = pd.read_excel(file)
    if df.empty:
        raise ValueError("Файл поставщиков пуст")

    df.columns = [str(col).strip().lower() for col in df.columns]
    required_cols = ['поставщик', 'контакт', 'срок доставки', 'цена доставки', 'минимальный заказ']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"В файле поставщиков не найдена колонка: {col}")

    session = get_session()
    try:
        now_date = datetime.now().date()
        filename = f"suppliers::{getattr(file, 'name', 'unknown_suppliers_file')}"
        _upsert_uploaded_file(session, filename, file_type='suppliers', date_from=now_date, date_to=now_date)

        for _, row in df.iterrows():
            name = str(row.get('поставщик', '')).strip()
            if not name:
                continue
            if _is_without_supplier_name(name):
                continue

            contact = str(row.get('контакт', '')).strip()
            delivery_time = str(row.get('срок доставки', '')).strip()
            delivery_cost = float(row.get('цена доставки', 0) or 0)
            min_order = float(row.get('минимальный заказ', 0) or 0)

            supplier = session.query(Supplier).filter_by(name=name).first()
            if not supplier:
                supplier = Supplier(
                    name=name,
                    contact=contact,
                    delivery_cost=delivery_cost,
                    delivery_time=delivery_time,
                    min_order=min_order,
                )
                session.add(supplier)
            else:
                supplier.contact = contact
                supplier.delivery_cost = delivery_cost
                supplier.delivery_time = delivery_time
                supplier.min_order = min_order

        session.commit()
    finally:
        session.close()


def save_price_list_file(file):
    """
    Parse and save price-list file.
    Structure:
      first 2 rows are header,
      B товар, E цена продажи, F цена закупки, G скидка, H упаковка, J поставщик
    Stores file in uploaded_files and updates suppliers/price_list_items/approximate_prices.
    """
    raw = pd.read_excel(file, header=None)
    if raw.empty or len(raw.index) <= 2:
        raise ValueError("Файл прайс-листа пуст или не содержит данных")

    # Required columns by index: B(1), E(4), F(5), G(6), H(7), J(9).
    # Extra columns are ignored.
    required_max_col = 9
    if raw.shape[1] <= required_max_col:
        raise ValueError("В прайс-листе не хватает обязательных колонок B, E, F, G, H, J")

    data = raw.iloc[2:, [1, 4, 5, 6, 7, 9]].copy()
    data.columns = ['sku', 'sale_price', 'purchase_price', 'discount', 'packaging', 'supplier_name']

    data['sku'] = data['sku'].fillna('').astype(str).str.strip()
    data['supplier_name'] = data['supplier_name'].fillna('').astype(str).str.strip()
    data['packaging'] = data['packaging'].fillna('').astype(str).str.strip()
    data['sale_price'] = pd.to_numeric(data['sale_price'], errors='coerce')
    data['purchase_price'] = pd.to_numeric(data['purchase_price'], errors='coerce')
    data['discount'] = pd.to_numeric(data['discount'], errors='coerce').fillna(0.0)

    data = data[(data['sku'] != '') & (data['supplier_name'] != '')]
    if data.empty:
        raise ValueError("В прайс-листе нет валидных строк")

    session = get_session()
    try:
        now_date = datetime.now().date()
        filename = f"price::{getattr(file, 'name', 'unknown_price_file')}"
        uploaded_file = _upsert_uploaded_file(session, filename, file_type='price', date_from=now_date, date_to=now_date)

        # Keep products aligned with main product list from logs.
        product_map = {p.sku: p.id for p in session.query(Product).all()}
        data = data[data['sku'].isin(product_map.keys())].copy()
        if data.empty:
            raise ValueError("В прайс-листе нет товаров из основного списка (логов)")

        # Ensure all suppliers from price list exist.
        suppliers = {}
        for name in sorted(set(data['supplier_name'])):
            supplier = session.query(Supplier).filter_by(name=name).first()
            if not supplier:
                supplier = Supplier(name=name)
                session.add(supplier)
                session.flush()
            suppliers[name] = supplier

        # If file is replaced, remove previous records from same file source.
        session.query(PriceListItem).filter_by(source_file_id=uploaded_file.id).delete()

        for _, row in data.iterrows():
            product_id = product_map[row['sku']]
            supplier = suppliers[row['supplier_name']]

            existing = session.query(PriceListItem).filter_by(
                product_id=product_id,
                supplier_id=supplier.id,
            ).first()

            sale_price = None if pd.isna(row['sale_price']) else float(row['sale_price'])
            purchase_price = None if pd.isna(row['purchase_price']) else float(row['purchase_price'])
            discount = None if pd.isna(row['discount']) else float(row['discount'])

            if existing:
                existing.sale_price = sale_price
                existing.purchase_price = purchase_price
                existing.discount = discount
                existing.packaging = row['packaging']
                existing.source_file_id = uploaded_file.id
            else:
                session.add(
                    PriceListItem(
                        product_id=product_id,
                        supplier_id=supplier.id,
                        sale_price=sale_price,
                        purchase_price=purchase_price,
                        discount=discount,
                        packaging=row['packaging'],
                        source_file_id=uploaded_file.id,
                    )
                )

        # Rebuild approximate prices from minimum purchase price.
        session.query(ApproximatePrice).delete()
        min_prices = (
            session.query(Product.sku, PriceListItem.purchase_price)
            .join(PriceListItem, PriceListItem.product_id == Product.id)
            .filter(PriceListItem.purchase_price.isnot(None))
            .all()
        )
        best = {}
        for sku, price in min_prices:
            if sku not in best or price < best[sku]:
                best[sku] = float(price)

        for sku, price in best.items():
            session.add(ApproximatePrice(sku=sku, price=price))

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
        suppliers = session.query(Supplier).filter(Supplier.name != 'Без поставщика').all()
        data = []
        for supplier in suppliers:
            item_count = session.query(PriceListItem).filter_by(supplier_id=supplier.id).count()
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
