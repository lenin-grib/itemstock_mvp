from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, ForeignKey, UniqueConstraint, Index, CheckConstraint, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import os
from datetime import datetime

Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    sku = Column(String, unique=True, nullable=False)
    first_seen = Column(DateTime, default=datetime.now, nullable=False)

class UploadedFile(Base):
    __tablename__ = 'uploaded_files'
    id = Column(Integer, primary_key=True)
    filename = Column(String, unique=True, nullable=False)
    upload_date = Column(DateTime, default=None)
    date_from = Column(Date, nullable=True)
    date_to = Column(Date, nullable=True)

class Sale(Base):
    __tablename__ = 'sales'
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    date = Column(Date, nullable=False)
    quantity = Column(Float, default=0, nullable=False)
    source_file_id = Column(Integer, ForeignKey('uploaded_files.id'))

    product = relationship("Product")
    source_file = relationship("UploadedFile")

    __table_args__ = (
        UniqueConstraint('product_id', 'date', name='unique_sale'),
        Index('idx_sale_product_date', 'product_id', 'date'),
        Index('idx_sale_source_file', 'source_file_id'),
    )

class Supply(Base):
    __tablename__ = 'supplies'
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    date = Column(Date, nullable=False)
    quantity = Column(Float, default=0, nullable=False)
    source_file_id = Column(Integer, ForeignKey('uploaded_files.id'))

    product = relationship("Product")
    source_file = relationship("UploadedFile")

    __table_args__ = (
        UniqueConstraint('product_id', 'date', name='unique_supply'),
        Index('idx_supply_product_date', 'product_id', 'date'),
    )

class Balance(Base):
    __tablename__ = 'balances'
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    date = Column(Date, nullable=False)
    balance = Column(Float, default=0, nullable=False)
    source_file_id = Column(Integer, ForeignKey('uploaded_files.id'))

    product = relationship("Product")
    source_file = relationship("UploadedFile")

    __table_args__ = (
        UniqueConstraint('product_id', 'date', name='unique_balance'),
        Index('idx_balance_product_date', 'product_id', 'date'),
        Index('idx_balance_latest', 'product_id', 'date'),
    )


class Spoil(Base):
    __tablename__ = 'spoils'
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    date = Column(Date, nullable=False)
    quantity = Column(Float, default=0, nullable=False)
    reason = Column(String, nullable=False)
    source_file_id = Column(Integer, ForeignKey('uploaded_files.id'))

    product = relationship("Product")
    source_file = relationship("UploadedFile")

    __table_args__ = (
        UniqueConstraint('product_id', 'date', 'reason', name='unique_spoil'),
        Index('idx_spoil_product_date', 'product_id', 'date'),
        Index('idx_spoil_source_file', 'source_file_id'),
    )

class Parameter(Base):
    __tablename__ = 'parameters'
    key = Column(String, primary_key=True)
    value = Column(Float, nullable=False)
    description = Column(String)

    __table_args__ = (
        CheckConstraint('value > 0', name='positive_value'),
    )

class Supplier(Base):
    __tablename__ = 'suppliers'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    contact = Column(String)
    delivery_cost = Column(Float, default=0.0)
    delivery_time = Column(String)
    min_order = Column(Float, default=0.0)

class SupplierItem(Base):
    __tablename__ = 'supplier_items'
    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    sku = Column(String, nullable=False)
    price = Column(Float, default=0.0, nullable=False)
    packaging = Column(String)

    supplier = relationship("Supplier")

    __table_args__ = (
        UniqueConstraint('supplier_id', 'sku', name='unique_supplier_sku'),
        Index('idx_supplier_item_supplier', 'supplier_id'),
    )

class NetSale(Base):
    """Pre-computed net sales: outbound minus spoils, per product per day."""
    __tablename__ = 'net_sales'
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    date = Column(Date, nullable=False)
    quantity = Column(Float, default=0, nullable=False)

    product = relationship("Product")

    __table_args__ = (
        UniqueConstraint('product_id', 'date', name='unique_net_sale'),
        Index('idx_net_sale_product_date', 'product_id', 'date'),
    )

class ApproximatePrice(Base):
    __tablename__ = 'approximate_prices'
    sku = Column(String, primary_key=True)
    price = Column(Float)

class CachedForecast(Base):
    __tablename__ = 'cached_forecasts'
    sku = Column(String, primary_key=True)
    whole_period_sales = Column(Float)
    sales_last_week = Column(Float)
    sales_last_month = Column(Float)
    trend_coef = Column(Float)
    forecast_next_week = Column(Integer)
    forecast_next_month = Column(Integer)
    last_updated = Column(DateTime, default=None)

    __table_args__ = (
        Index('idx_cached_forecast_updated', 'last_updated'),
    )

class CachedIdealStock(Base):
    __tablename__ = 'cached_ideal_stock'
    sku = Column(String, primary_key=True)
    current_stock = Column(Integer)
    ideal_stock = Column(Integer)
    monthly_ideal_stock = Column(Integer)
    to_order_week = Column(Integer)
    to_order_month = Column(Integer)
    last_updated = Column(DateTime, default=None)

    __table_args__ = (
        Index('idx_cached_ideal_stock_updated', 'last_updated'),
    )

# Database setup
DATABASE_URL = "sqlite:///app.db"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    # Initialize default parameters if not exist
    session = SessionLocal()
    try:
        # Lightweight migration for existing SQLite DBs.
        existing_cols = {
            row[1] for row in session.execute(text("PRAGMA table_info(uploaded_files)")).fetchall()
        }
        if 'date_from' not in existing_cols:
            session.execute(text("ALTER TABLE uploaded_files ADD COLUMN date_from DATE"))
        if 'date_to' not in existing_cols:
            session.execute(text("ALTER TABLE uploaded_files ADD COLUMN date_to DATE"))

        params = [
            ('quote_multiplicator', 1.5, 'Коэффициент запаса'),
            ('min_items_in_stock', 5, 'Минимальный запас на складе'),
            ('trend_period_weeks', 8, 'Период для расчёта тренда (недели)')
        ]
        for key, value, desc in params:
            if not session.query(Parameter).filter_by(key=key).first():
                session.add(Parameter(key=key, value=value, description=desc))

        # Backward compatibility: migrate old months-based parameter if present.
        old_param = session.query(Parameter).filter_by(key='trend_period_months').first()
        weeks_param = session.query(Parameter).filter_by(key='trend_period_weeks').first()
        if old_param and weeks_param and (weeks_param.value is None or weeks_param.value <= 0):
            weeks_param.value = max(1, int(old_param.value * 4))
        session.commit()
    finally:
        session.close()

if not os.path.exists('app.db'):
    init_db()