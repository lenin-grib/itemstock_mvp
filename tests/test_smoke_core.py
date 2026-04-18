import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database
import db_utils
import forecast
import ideal_stock
import order_service
import parser
import supplier_service


_SUPPLIER_QUERY_UNSET = object()


class _FakeChainQuery:
    def __init__(self, rows):
        self._rows = rows

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeSupplierQuery:
    def __init__(self, supplier):
        self._supplier = supplier

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self._supplier


class _FakeSession:
    def __init__(self, rows=None, supplier=_SUPPLIER_QUERY_UNSET):
        self.rows = rows or []
        self.supplier = supplier
        self.committed = False
        self.closed = False

    def query(self, *args, **kwargs):
        # update_supplier_info asks for query(Supplier)
        if self.supplier is not _SUPPLIER_QUERY_UNSET and len(args) == 1:
            return _FakeSupplierQuery(self.supplier)
        # order_service asks a long chain with .all()
        return _FakeChainQuery(self.rows)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class ForecastSmokeTests(unittest.TestCase):
    def test_get_last_n_days_sales_inclusive_window(self):
        raw_df = pd.DataFrame(
            {
                "sku": ["A", "A", "A"],
                "date": pd.to_datetime(["2026-04-08", "2026-04-09", "2026-04-10"]),
                "outbound": [1, 2, 3],
            }
        )

        result = forecast.get_last_n_days_sales(
            raw_df,
            "A",
            n_days=2,
            reference_date=pd.Timestamp("2026-04-10"),
        )

        self.assertEqual(result, 5)

    def test_get_sales_interval_invalid_bounds_raise_value_error(self):
        raw_df = pd.DataFrame(
            {
                "sku": ["A"],
                "date": pd.to_datetime(["2026-04-10"]),
                "outbound": [1],
            }
        )

        with self.assertRaises(ValueError):
            forecast.get_sales_interval(
                raw_df,
                "A",
                start_day=0,
                end_day=-7,
                reference_date=pd.Timestamp("2026-04-10"),
            )

    def test_get_sales_interval_includes_both_interval_bounds(self):
        raw_df = pd.DataFrame(
            {
                "sku": ["A", "A", "A", "A"],
                "date": pd.to_datetime(["2026-04-03", "2026-04-04", "2026-04-09", "2026-04-10"]),
                "outbound": [1, 2, 3, 4],
            }
        )

        result = forecast.get_sales_interval(
            raw_df,
            "A",
            start_day=-7,
            end_day=-1,
            reference_date=pd.Timestamp("2026-04-10"),
        )

        # Interval should include all dates from 2026-04-03 through 2026-04-09.
        self.assertEqual(result, 6)

    @patch("forecast.save_forecast_cache")
    @patch("forecast.get_all_skus", return_value=["A"]) 
    @patch("forecast.get_net_sales_data", return_value=pd.DataFrame(columns=["sku", "date", "outbound"]))
    def test_calculate_trend_and_forecast_empty_raw_returns_zero_row(self, _mock_raw, _mock_skus, mock_save):
        result = forecast.calculate_trend_and_forecast(trend_period_weeks=8)

        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual(row["sku"], "A")
        self.assertEqual(row["whole_period_sales"], 0)
        self.assertEqual(row["whole_period_forecast"], 0)
        mock_save.assert_called_once()

    @patch("forecast.save_forecast_cache")
    @patch("forecast.get_all_skus", return_value=["A", "B"]) 
    @patch("forecast.get_net_sales_data")
    def test_calculate_trend_and_forecast_uses_global_reference_date(self, mock_raw, _mock_skus, _mock_save):
        reference_date = pd.Timestamp("2026-04-25")
        a_dates = pd.date_range(end=reference_date, periods=56, freq="D")
        b_dates = pd.date_range(start="2026-03-20", end="2026-04-10", freq="D")
        mock_raw.return_value = pd.DataFrame(
            {
                "sku": ["A"] * len(a_dates) + ["B"] * len(b_dates),
                "date": list(a_dates) + list(b_dates),
                "outbound": [1] * len(a_dates) + [1] * len(b_dates),
            }
        )

        result = forecast.calculate_trend_and_forecast(trend_period_weeks=8)
        a_row = result.loc[result["sku"] == "A"].iloc[0]
        b_row = result.loc[result["sku"] == "B"].iloc[0]

        self.assertEqual(a_row["whole_period_sales"], 56)
        self.assertEqual(int(a_row[["sales_interval_m1w", "sales_interval_m2w", "sales_interval_m3w", "sales_interval_m4w"]].sum()), 28)
        self.assertLess(b_row["whole_period_sales"], a_row["whole_period_sales"])

    @patch("forecast.save_forecast_cache")
    @patch("forecast.get_all_skus", return_value=["A"])
    @patch("forecast.get_net_sales_data")
    def test_calculate_trend_and_forecast_whole_period_depends_on_trend_weeks(self, mock_raw, _mock_skus, _mock_save):
        dates = pd.date_range(end=pd.Timestamp("2026-04-30"), periods=70, freq="D")
        mock_raw.return_value = pd.DataFrame(
            {
                "sku": ["A"] * len(dates),
                "date": list(dates),
                "outbound": [1] * len(dates),
            }
        )

        result_4w = forecast.calculate_trend_and_forecast(trend_period_weeks=4)
        result_8w = forecast.calculate_trend_and_forecast(trend_period_weeks=8)

        self.assertEqual(int(result_4w.iloc[0]["whole_period_sales"]), 28)
        self.assertEqual(int(result_8w.iloc[0]["whole_period_sales"]), 56)

    @patch("forecast.calculate_trend_and_forecast")
    @patch("forecast.get_cached_forecasts")
    def test_get_forecasts_prefers_cache_when_available(self, mock_cached, mock_recalc):
        mock_cached.return_value = pd.DataFrame(
            [{"sku": "A", "whole_period_sales": 1, "last_updated": pd.Timestamp("2026-04-18")}]
        )

        result = forecast.get_forecasts(trend_period_weeks=6)

        self.assertIn("sku", result.columns)
        mock_recalc.assert_not_called()

    @patch("forecast.calculate_trend_and_forecast")
    @patch("forecast.get_cached_forecasts", return_value=pd.DataFrame())
    def test_get_forecasts_recalculates_on_cache_miss(self, _mock_cached, mock_recalc):
        mock_recalc.return_value = pd.DataFrame([{"sku": "A", "whole_period_sales": 2}])

        result = forecast.get_forecasts(trend_period_weeks=6)

        self.assertEqual(list(result["sku"]), ["A"])
        mock_recalc.assert_called_once_with(trend_period_weeks=6)


class IdealStockSmokeTests(unittest.TestCase):
    @patch("ideal_stock.save_ideal_stock_cache")
    @patch("ideal_stock.get_parameters", return_value={"trend_period_weeks": 8, "quote_multiplicator": 1.0, "min_items_in_stock": 5})
    def test_calculate_ideal_stock_basic_flow(self, _mock_params, _mock_save):
        forecast_df = pd.DataFrame(
            {
                "sku": ["A"],
                "forecast_interval_p1w": [10],
                "forecast_interval_p2w": [10],
                "forecast_interval_p3w": [10],
                "forecast_interval_p4w": [10],
                "whole_period_forecast": [40],
            }
        )
        stock_df = pd.DataFrame({"sku": ["A"], "current_stock": [3]})

        result = ideal_stock.calculate_ideal_stock(forecast_df=forecast_df, stock_df=stock_df)
        row = result.iloc[0]

        self.assertEqual(row["ideal_stock"], 15)
        self.assertEqual(row["to_order_week"], 12)
        self.assertEqual(row["monthly_ideal_stock"], 45)

    @patch("ideal_stock.save_ideal_stock_cache")
    @patch("ideal_stock.get_parameters", return_value={"trend_period_weeks": 8, "quote_multiplicator": 1.0, "min_items_in_stock": 5})
    def test_calculate_ideal_stock_handles_missing_stock_columns(self, _mock_params, _mock_save):
        forecast_df = pd.DataFrame(
            {
                "sku": ["A"],
                "forecast_interval_p1w": [2],
                "forecast_interval_p2w": [0],
                "forecast_interval_p3w": [0],
                "forecast_interval_p4w": [0],
                "whole_period_forecast": [2],
            }
        )
        stock_df = pd.DataFrame({"x": [1]})

        result = ideal_stock.calculate_ideal_stock(forecast_df=forecast_df, stock_df=stock_df)

        self.assertEqual(result.iloc[0]["current_stock"], 0)
        self.assertGreaterEqual(result.iloc[0]["to_order_week"], 0)

    @patch("ideal_stock.save_ideal_stock_cache")
    @patch("ideal_stock.get_parameters", return_value={"trend_period_weeks": 8, "quote_multiplicator": 1.0, "min_items_in_stock": 5})
    def test_calculate_ideal_stock_zeroes_items_without_recent_sales(self, _mock_params, _mock_save):
        forecast_df = pd.DataFrame(
            {
                "sku": ["A", "B"],
                "forecast_interval_p1w": [5, 5],
                "forecast_interval_p2w": [5, 5],
                "forecast_interval_p3w": [5, 5],
                "forecast_interval_p4w": [5, 5],
                "whole_period_forecast": [20, 20],
            }
        )
        stock_df = pd.DataFrame({"sku": ["A", "B"], "current_stock": [0, 0]})
        sales_df = pd.DataFrame(
            {
                "sku": ["A"],
                "date": pd.to_datetime(["2026-04-01"]),
                "sales": [10],
            }
        )

        result = ideal_stock.calculate_ideal_stock(forecast_df=forecast_df, stock_df=stock_df, sales_df=sales_df)
        b_row = result.loc[result["sku"] == "B"].iloc[0]
        self.assertEqual(b_row["ideal_stock"], 0)
        self.assertEqual(b_row["to_order_week"], 0)

    @patch("ideal_stock.calculate_ideal_stock")
    @patch("ideal_stock.get_cached_ideal_stock")
    def test_get_ideal_stock_prefers_cache_when_available(self, mock_cached, mock_calc):
        mock_cached.return_value = pd.DataFrame([{"sku": "A", "to_order_month": 1}])

        result = ideal_stock.get_ideal_stock()

        self.assertEqual(list(result["sku"]), ["A"])
        mock_calc.assert_not_called()

    @patch("ideal_stock.calculate_ideal_stock")
    @patch("ideal_stock.get_cached_ideal_stock", return_value=pd.DataFrame())
    def test_get_ideal_stock_recalculates_on_cache_miss(self, _mock_cached, mock_calc):
        mock_calc.return_value = pd.DataFrame([{"sku": "A", "to_order_month": 2}])

        result = ideal_stock.get_ideal_stock()

        self.assertEqual(list(result["sku"]), ["A"])
        mock_calc.assert_called_once()


class OrderAndSupplierSmokeTests(unittest.TestCase):
    def test_parse_packaging_units_edge_cases(self):
        self.assertEqual(order_service._parse_packaging_units(None), 1)
        self.assertEqual(order_service._parse_packaging_units(""), 1)
        self.assertEqual(order_service._parse_packaging_units("0"), 1)
        self.assertEqual(order_service._parse_packaging_units("уп 6 шт"), 6)

    def test_build_recommended_orders_selects_cheapest_and_reports_missing(self):
        rows = [
            # sku, supplier_id, supplier_name, delivery_cost, delivery_time, min_order, purchase_price, packaging
            ("A", 1, "S1", 100.0, "2", 1000.0, 20.0, "6"),
            ("A", 2, "S2", 50.0, "1", 0.0, 10.0, "6"),
        ]
        fake_session = _FakeSession(rows=rows)
        order_df = pd.DataFrame(
            {
                "sku": ["A", "B"],
                "to_order_month": [6, 5],
            }
        )

        with patch("order_service.get_session", return_value=fake_session):
            orders, missing, warnings, zero_price_warnings = order_service.build_recommended_orders(
                order_df,
                period_weeks=4,
                include_zero_price_warnings=True,
            )

        self.assertEqual(missing, ["B"])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["supplier_name"], "S2")
        # Current logic rounds strictly above required qty for pack multiples (6 -> 12)
        self.assertEqual(orders[0]["items"][0]["Количество для заказа"], 12)
        self.assertEqual(warnings, [])
        self.assertEqual(zero_price_warnings, [])

    def test_build_recommended_orders_emits_zero_price_warning(self):
        rows = [
            # sku, supplier_id, supplier_name, delivery_cost, delivery_time, min_order, purchase_price, packaging
            ("A", 1, "S1", 100.0, "2", 0.0, 0.0, "6"),
        ]
        fake_session = _FakeSession(rows=rows)
        order_df = pd.DataFrame(
            {
                "sku": ["A"],
                "to_order_month": [6],
            }
        )

        with patch("order_service.get_session", return_value=fake_session):
            orders, missing, warnings, zero_price_warnings = order_service.build_recommended_orders(
                order_df,
                period_weeks=4,
                include_zero_price_warnings=True,
            )

        self.assertEqual(missing, [])
        self.assertEqual(len(orders), 1)
        self.assertEqual(warnings, [])
        self.assertEqual(len(zero_price_warnings), 1)
        self.assertEqual(zero_price_warnings[0]["supplier_name"], "S1")
        self.assertEqual(zero_price_warnings[0]["items"], ["A"])

    def test_build_recommended_orders_default_contract_returns_three_values(self):
        rows = [
            ("A", 1, "S1", 100.0, "2", 0.0, 10.0, "6"),
        ]
        fake_session = _FakeSession(rows=rows)
        order_df = pd.DataFrame(
            {
                "sku": ["A"],
                "to_order_month": [6],
            }
        )

        with patch("order_service.get_session", return_value=fake_session):
            result = order_service.build_recommended_orders(order_df, period_weeks=4)

        self.assertEqual(len(result), 3)

    def test_build_recommended_orders_contract_structure(self):
        rows = [
            ("A", 1, "S1", 100.0, "2", 0.0, 10.0, "6"),
        ]
        fake_session = _FakeSession(rows=rows)
        order_df = pd.DataFrame(
            {
                "sku": ["A"],
                "to_order_month": [6],
            }
        )

        with patch("order_service.get_session", return_value=fake_session):
            orders, missing, warnings = order_service.build_recommended_orders(order_df, period_weeks=4)

        self.assertEqual(missing, [])
        self.assertEqual(warnings, [])
        self.assertEqual(len(orders), 1)

        order = orders[0]
        self.assertIn("supplier_name", order)
        self.assertIn("subtotal_without_delivery", order)
        self.assertIn("total_cost", order)
        self.assertIn("items", order)

        self.assertEqual(len(order["items"]), 1)
        item = order["items"][0]
        self.assertIn("Товар", item)
        self.assertIn("Количество для заказа", item)
        self.assertIn("Цена за единицу", item)
        self.assertIn("Стоимость", item)

    def test_update_supplier_info_updates_and_commits(self):
        class SupplierObj:
            def __init__(self):
                self.delivery_cost = 0
                self.delivery_time = ""
                self.min_order = 0

        supplier_obj = SupplierObj()
        fake_session = _FakeSession(supplier=supplier_obj)

        with patch("supplier_service.get_session", return_value=fake_session):
            supplier_service.update_supplier_info("Name", 120.5, "3", 500)

        self.assertTrue(fake_session.committed)
        self.assertTrue(fake_session.closed)
        self.assertEqual(supplier_obj.delivery_cost, 120.5)
        self.assertEqual(supplier_obj.delivery_time, "3")
        self.assertEqual(supplier_obj.min_order, 500.0)

    def test_update_supplier_info_no_commit_when_supplier_not_found(self):
        fake_session = _FakeSession(supplier=None)

        with patch("supplier_service.get_session", return_value=fake_session):
            supplier_service.update_supplier_info("Missing", 1, "1", 1)

        self.assertFalse(fake_session.committed)
        self.assertTrue(fake_session.closed)


class ParserSmokeTests(unittest.TestCase):
    def test_parse_and_save_file_loads_new_product_log(self):
        class FakeFile:
            name = "new_product_log.xlsx"

        parsed_df = pd.DataFrame(
            {
                "sku": ["NEW-SKU-001"],
                "date": [pd.Timestamp("2026-04-18")],
                "inbound": [10],
                "outbound": [2],
                "остаток на складе": [8],
            }
        )

        with patch("parser.parse_single_file", return_value=parsed_df) as mock_parse, patch(
            "parser.save_parsed_data"
        ) as mock_save:
            parser.parse_and_save_file(FakeFile())

        mock_parse.assert_called_once()
        mock_save.assert_called_once()
        saved_df, saved_filename = mock_save.call_args[0]
        self.assertEqual(saved_filename, "new_product_log.xlsx")
        self.assertEqual(list(saved_df["sku"]), ["NEW-SKU-001"])


class DbUtilsIntegrationSmokeTests(unittest.TestCase):
    def test_save_parsed_data_creates_new_product_for_new_log_sku(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            engine = create_engine(f"sqlite:///{db_path}")
            local_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            database.Base.metadata.create_all(bind=engine)

            input_df = pd.DataFrame(
                {
                    "sku": ["NEW-SKU-DB-001"],
                    "date": [pd.Timestamp("2026-04-18")],
                    "inbound": [10],
                    "outbound": [3],
                    "остаток на складе": [7],
                }
            )

            with patch("db_utils.SessionLocal", local_session):
                db_utils.save_parsed_data(input_df, "integration_new_product_log.xlsx")

            session = local_session()
            try:
                created_product = session.query(database.Product).filter_by(sku="NEW-SKU-DB-001").first()
                self.assertIsNotNone(created_product)

                uploaded = session.query(database.UploadedFile).filter_by(
                    filename="integration_new_product_log.xlsx"
                ).first()
                self.assertIsNotNone(uploaded)
                self.assertEqual(uploaded.file_type, "logs")

                sale_row = session.query(database.Sale).filter_by(product_id=created_product.id).first()
                self.assertIsNotNone(sale_row)
                self.assertEqual(float(sale_row.quantity), 3.0)
            finally:
                session.close()
                engine.dispose()

    def test_save_spoils_data_recalculates_net_sales_for_sku_date(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            engine = create_engine(f"sqlite:///{db_path}")
            local_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            database.Base.metadata.create_all(bind=engine)

            sales_input_df = pd.DataFrame(
                {
                    "sku": ["SKU-SPOIL-001"],
                    "date": [pd.Timestamp("2026-04-18")],
                    "inbound": [0],
                    "outbound": [10],
                    "остаток на складе": [5],
                }
            )
            spoils_input_df = pd.DataFrame(
                {
                    "sku": ["SKU-SPOIL-001"],
                    "date": [pd.Timestamp("2026-04-18")],
                    "quantity": [3],
                    "reason": ["damaged"],
                }
            )

            with patch("db_utils.SessionLocal", local_session):
                db_utils.save_parsed_data(sales_input_df, "sales_for_spoil_case.xlsx")
                db_utils.save_spoils_data(spoils_input_df, "spoils_for_spoil_case.xlsx")

            session = local_session()
            try:
                product = session.query(database.Product).filter_by(sku="SKU-SPOIL-001").first()
                self.assertIsNotNone(product)

                spoil_row = session.query(database.Spoil).filter_by(product_id=product.id).first()
                self.assertIsNotNone(spoil_row)
                self.assertEqual(float(spoil_row.quantity), 3.0)

                net_sale_row = session.query(database.NetSale).filter_by(product_id=product.id).first()
                self.assertIsNotNone(net_sale_row)
                self.assertEqual(float(net_sale_row.quantity), 7.0)
            finally:
                session.close()
                engine.dispose()


if __name__ == "__main__":
    unittest.main()