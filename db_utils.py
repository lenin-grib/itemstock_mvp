from database import SessionLocal, Product, UploadedFile, Sale, Supply, Balance, Spoil, NetSale, Parameter, CachedForecast, CachedIdealStock, Supplier, SupplierItem, ApproximatePrice
from datetime import datetime
import pandas as pd
from sqlalchemy import func

def get_session():
    return SessionLocal()

def get_uploaded_files():
    session = get_session()
    try:
        files = session.query(UploadedFile).all()
        return [(f.id, f.filename, f.file_type, f.upload_date, f.date_from, f.date_to) for f in files]
    finally:
        session.close()


def _source_max_date(session, model, source_file_id):
    if source_file_id is None:
        return None
    return session.query(func.max(model.date)).filter(model.source_file_id == source_file_id).scalar()


def _is_newer_source(session, model, existing_source_file_id, new_file, new_file_last_date):
    if existing_source_file_id is None:
        return True

    existing_file = session.query(UploadedFile).filter_by(id=existing_source_file_id).first()
    if existing_file is None:
        return True

    existing_last_date = _source_max_date(session, model, existing_source_file_id)
    if existing_last_date is None:
        return True

    if new_file_last_date > existing_last_date:
        return True
    if new_file_last_date < existing_last_date:
        return False

    return (new_file.upload_date or datetime.min) >= (existing_file.upload_date or datetime.min)


def save_parsed_data(df, filename):
    session = get_session()
    try:
        work_df = df.copy()
        work_df['date'] = pd.to_datetime(work_df['date']).dt.date
        work_df['inbound'] = pd.to_numeric(work_df.get('inbound', 0), errors='coerce').fillna(0.0)
        work_df['outbound'] = pd.to_numeric(work_df.get('outbound', 0), errors='coerce').fillna(0.0)
        work_df['\u043e\u0441\u0442\u0430\u0442\u043e\u043a \u043d\u0430 \u0441\u043a\u043b\u0430\u0434\u0435'] = pd.to_numeric(work_df.get('\u043e\u0441\u0442\u0430\u0442\u043e\u043a \u043d\u0430 \u0441\u043a\u043b\u0430\u0434\u0435', 0), errors='coerce').fillna(0.0)
        work_df = (
            work_df.sort_values(['sku', 'date'])
            .groupby(['sku', 'date'], as_index=False)
            .agg({
                'inbound': 'sum',
                'outbound': 'sum',
                '\u043e\u0441\u0442\u0430\u0442\u043e\u043a \u043d\u0430 \u0441\u043a\u043b\u0430\u0434\u0435': 'last',
            })
        )
        file_first_date = work_df['date'].min() if not work_df.empty else None
        file_last_date = work_df['date'].max()

        existing_file = session.query(UploadedFile).filter_by(filename=filename).first()
        if existing_file:
            session.query(Sale).filter_by(source_file_id=existing_file.id).delete()
            session.query(Supply).filter_by(source_file_id=existing_file.id).delete()
            session.query(Balance).filter_by(source_file_id=existing_file.id).delete()
            existing_file.file_type = 'logs'
            existing_file.upload_date = datetime.now()
            existing_file.date_from = file_first_date
            existing_file.date_to = file_last_date
            uploaded_file = existing_file
        else:
            uploaded_file = UploadedFile(
                filename=filename,
                file_type='logs',
                upload_date=datetime.now(),
                date_from=file_first_date,
                date_to=file_last_date,
            )
            session.add(uploaded_file)
        session.flush()

        for _, row in work_df.iterrows():
            sku = row['sku']
            date = row['date']

            product = session.query(Product).filter_by(sku=sku).first()
            if not product:
                product = Product(sku=sku, first_seen=datetime.now())
                session.add(product)
                session.flush()

            existing_sale = session.query(Sale).filter_by(product_id=product.id, date=date).first()
            can_overwrite_sale = _is_newer_source(
                session, Sale,
                existing_sale.source_file_id if existing_sale else None,
                uploaded_file, file_last_date,
            )
            if can_overwrite_sale:
                outbound_qty = float(row.get('outbound', 0) or 0)
                if outbound_qty > 0:
                    if existing_sale:
                        existing_sale.quantity = outbound_qty
                        existing_sale.source_file_id = uploaded_file.id
                    else:
                        session.add(Sale(product_id=product.id, date=date, quantity=outbound_qty, source_file_id=uploaded_file.id))
                else:
                    if existing_sale:
                        session.delete(existing_sale)

            existing_supply = session.query(Supply).filter_by(product_id=product.id, date=date).first()
            can_overwrite_supply = _is_newer_source(
                session, Supply,
                existing_supply.source_file_id if existing_supply else None,
                uploaded_file, file_last_date,
            )
            if can_overwrite_supply:
                inbound_qty = float(row.get('inbound', 0) or 0)
                if inbound_qty > 0:
                    if existing_supply:
                        existing_supply.quantity = inbound_qty
                        existing_supply.source_file_id = uploaded_file.id
                    else:
                        session.add(Supply(product_id=product.id, date=date, quantity=inbound_qty, source_file_id=uploaded_file.id))
                else:
                    if existing_supply:
                        session.delete(existing_supply)

            existing_balance = session.query(Balance).filter_by(product_id=product.id, date=date).first()
            can_overwrite_balance = _is_newer_source(
                session, Balance,
                existing_balance.source_file_id if existing_balance else None,
                uploaded_file, file_last_date,
            )
            if can_overwrite_balance:
                new_balance = float(row.get('\u043e\u0441\u0442\u0430\u0442\u043e\u043a \u043d\u0430 \u0441\u043a\u043b\u0430\u0434\u0435', 0) or 0)
                if existing_balance:
                    existing_balance.balance = new_balance
                    existing_balance.source_file_id = uploaded_file.id
                else:
                    session.add(Balance(product_id=product.id, date=date, balance=new_balance, source_file_id=uploaded_file.id))

        session.commit()
        rebuild_net_sales()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def save_spoils_data(df, filename):
    session = get_session()
    try:
        work_df = df.copy()
        work_df['date'] = pd.to_datetime(work_df['date']).dt.date
        work_df['quantity'] = pd.to_numeric(work_df.get('quantity', 0), errors='coerce').fillna(0.0)
        work_df['reason'] = work_df.get('reason', '').fillna('').astype(str).str.strip()
        work_df = (
            work_df.groupby(['sku', 'date', 'reason'], as_index=False)
            .agg({'quantity': 'sum'})
        )
        file_first_date = work_df['date'].min() if not work_df.empty else None
        file_last_date = work_df['date'].max()

        spoils_filename = f"spoils::{filename}"
        existing_file = session.query(UploadedFile).filter_by(filename=spoils_filename).first()
        if existing_file:
            session.query(Spoil).filter_by(source_file_id=existing_file.id).delete()
            existing_file.file_type = 'spoils'
            existing_file.upload_date = datetime.now()
            existing_file.date_from = file_first_date
            existing_file.date_to = file_last_date
            uploaded_file = existing_file
        else:
            uploaded_file = UploadedFile(
                filename=spoils_filename,
                file_type='spoils',
                upload_date=datetime.now(),
                date_from=file_first_date,
                date_to=file_last_date,
            )
            session.add(uploaded_file)
        session.flush()

        for _, row in work_df.iterrows():
            sku = row['sku']
            date = row['date']
            reason = row.get('reason') or '\u0411\u0435\u0437 \u043f\u0440\u0438\u0447\u0438\u043d\u044b'
            qty = float(row.get('quantity', 0) or 0)

            product = session.query(Product).filter_by(sku=sku).first()
            if not product:
                product = Product(sku=sku, first_seen=datetime.now())
                session.add(product)
                session.flush()

            existing_spoil = session.query(Spoil).filter_by(product_id=product.id, date=date, reason=reason).first()
            can_overwrite_spoil = _is_newer_source(
                session, Spoil,
                existing_spoil.source_file_id if existing_spoil else None,
                uploaded_file, file_last_date,
            )
            if not can_overwrite_spoil:
                continue

            if existing_spoil:
                existing_spoil.quantity = qty
                existing_spoil.source_file_id = uploaded_file.id
            else:
                session.add(Spoil(product_id=product.id, date=date, quantity=qty, reason=reason, source_file_id=uploaded_file.id))

        session.commit()
        rebuild_net_sales()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def rebuild_net_sales(session=None):
    """Recomputes net_sales as (sale - spoils) per product per day, clipped at 0."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        sales_rows = session.query(Sale.product_id, Sale.date, Sale.quantity).all()
        sales_df = pd.DataFrame(
            [(r.product_id, r.date, float(r.quantity or 0)) for r in sales_rows],
            columns=['product_id', 'date', 'quantity']
        )

        spoils_rows = (
            session.query(Spoil.product_id, Spoil.date, func.sum(Spoil.quantity))
            .group_by(Spoil.product_id, Spoil.date)
            .all()
        )
        spoils_df = pd.DataFrame(
            [(r[0], r[1], float(r[2] or 0)) for r in spoils_rows],
            columns=['product_id', 'date', 'spoil_qty']
        )

        if sales_df.empty:
            session.query(NetSale).delete()
            if own_session:
                session.commit()
            return

        if not spoils_df.empty:
            merged = sales_df.merge(spoils_df, on=['product_id', 'date'], how='left')
            merged['spoil_qty'] = merged['spoil_qty'].fillna(0)
        else:
            merged = sales_df.copy()
            merged['spoil_qty'] = 0.0

        merged['net_qty'] = (merged['quantity'] - merged['spoil_qty']).clip(lower=0)

        for _, row in merged.iterrows():
            existing = session.query(NetSale).filter_by(
                product_id=int(row['product_id']), date=row['date']
            ).first()
            net_qty = float(row['net_qty'])
            if existing:
                existing.quantity = net_qty
            else:
                session.add(NetSale(product_id=int(row['product_id']), date=row['date'], quantity=net_qty))

        current_keys = set(zip(merged['product_id'].astype(int), merged['date']))
        for ns in session.query(NetSale).all():
            if (ns.product_id, ns.date) not in current_keys:
                session.delete(ns)

        if own_session:
            session.commit()
    except Exception:
        if own_session:
            session.rollback()
        raise
    finally:
        if own_session:
            session.close()


def get_net_sales_data():
    """Returns pre-computed net sales as DataFrame[sku, date, outbound]."""
    session = get_session()
    try:
        rows = session.query(NetSale, Product.sku).join(Product).all()

        # Backfill for existing databases: if net_sales is empty but raw sales exist,
        # rebuild once and read again.
        if not rows and session.query(Sale.id).first() is not None:
            rebuild_net_sales(session=session)
            rows = session.query(NetSale, Product.sku).join(Product).all()

        data = [{'sku': sku, 'date': ns.date, 'outbound': float(ns.quantity or 0)} for ns, sku in rows]
        df = pd.DataFrame(data)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
        return df
    finally:
        session.close()


def get_sales_data():
    session = get_session()
    try:
        sales_query = session.query(Sale, Product.sku).join(Product).all()
        sales_data = []
        for sale, sku in sales_query:
            sales_data.append({'sku': sku, 'date': sale.date, 'outbound': float(sale.quantity or 0)})
        sales_df = pd.DataFrame(sales_data)

        spoils_query = session.query(Spoil, Product.sku).join(Product).all()
        spoils_data = []
        for spoil, sku in spoils_query:
            spoils_data.append({'sku': sku, 'date': spoil.date, 'spoil_qty': float(spoil.quantity or 0)})
        spoils_df = pd.DataFrame(spoils_data)

        if sales_df.empty:
            return pd.DataFrame(columns=['sku', 'date', 'outbound'])

        sales_df['date'] = pd.to_datetime(sales_df['date'])

        if spoils_df.empty:
            return sales_df

        spoils_df['date'] = pd.to_datetime(spoils_df['date'])
        spoils_df = spoils_df.groupby(['sku', 'date'], as_index=False)['spoil_qty'].sum()

        merged = sales_df.merge(spoils_df, on=['sku', 'date'], how='left')
        merged['spoil_qty'] = merged['spoil_qty'].fillna(0)
        merged['outbound'] = (merged['outbound'] - merged['spoil_qty']).clip(lower=0)

        return merged[['sku', 'date', 'outbound']]
    finally:
        session.close()


def get_spoils_data():
    session = get_session()
    try:
        query = session.query(Spoil, Product.sku).join(Product).all()
        data = []
        for spoil, sku in query:
            data.append({'sku': sku, 'date': spoil.date, 'quantity': float(spoil.quantity or 0), 'reason': spoil.reason})
        df = pd.DataFrame(data)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values(['date', 'sku', 'reason'], ascending=[False, True, True])
        return df
    finally:
        session.close()


def get_approximate_prices():
    session = get_session()
    try:
        prices = session.query(ApproximatePrice).all()
        data = [{'sku': p.sku, 'price': p.price} for p in prices]
        return pd.DataFrame(data) if data else pd.DataFrame()
    finally:
        session.close()


def get_current_stock():
    session = get_session()
    try:
        subquery = session.query(
            Balance.product_id,
            Balance.balance,
            func.row_number().over(
                partition_by=Balance.product_id,
                order_by=Balance.date.desc()
            ).label('rn')
        ).subquery()

        query = session.query(
            subquery.c.product_id,
            subquery.c.balance,
            Product.sku
        ).join(Product, subquery.c.product_id == Product.id).filter(subquery.c.rn == 1).all()

        data = [{'sku': sku, 'current_stock': balance} for _, balance, sku in query]
        return pd.DataFrame(data)
    finally:
        session.close()


def get_all_skus():
    session = get_session()
    try:
        products = session.query(Product).all()
        return [p.sku for p in products]
    finally:
        session.close()


def get_parameters():
    session = get_session()
    try:
        params = session.query(Parameter).all()
        return {param.key: param.value for param in params}
    finally:
        session.close()


def update_parameter(key, value):
    session = get_session()
    try:
        param = session.query(Parameter).filter_by(key=key).first()
        if param:
            param.value = value
            session.commit()
    finally:
        session.close()