from dataclasses import dataclass, field

from order_service import build_recommended_orders


@dataclass
class OrdersViewModel:
    recommended_orders: list[dict] = field(default_factory=list)
    missing_supplier_skus: list[str] = field(default_factory=list)
    below_min_map: dict[str, dict] = field(default_factory=dict)
    zero_price_map: dict[str, dict] = field(default_factory=dict)


def build_orders_view_model(order_df, period_weeks=4):
    """Build UI-ready data for recommended orders section without Streamlit dependencies."""
    recommended_result = build_recommended_orders(
        order_df,
        period_weeks=period_weeks,
        return_result_object=True,
    )

    below_min_map = {
        w['supplier_name']: w for w in recommended_result.below_min_order_warnings
    }
    zero_price_map = {
        w['supplier_name']: w for w in recommended_result.zero_price_warnings
    }

    recommended_orders = sorted(
        recommended_result.orders,
        key=lambda x: (1 if x.get('is_without_supplier') else 0, -x['total_cost'])
    )

    return OrdersViewModel(
        recommended_orders=recommended_orders,
        missing_supplier_skus=recommended_result.missing_supplier_skus,
        below_min_map=below_min_map,
        zero_price_map=zero_price_map,
    )
