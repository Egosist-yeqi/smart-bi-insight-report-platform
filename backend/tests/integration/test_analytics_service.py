from datetime import date
from decimal import Decimal

from app.analytics.schemas import DashboardFilters
from app.analytics.service import detect_anomalies, forecast_next_month, get_dashboard
from app.db.models import SalesOrder


def _order(
    external_order_id: str, order_date: date, amount: Decimal, region: str
) -> SalesOrder:
    return SalesOrder(
        external_order_id=external_order_id,
        order_date=order_date,
        region=region,
        province="测试省",
        product_id=1,
        product_name="测试产品",
        category="测试分类",
        customer_type="测试客户",
        quantity=1,
        amount=amount,
        profit=amount / Decimal("10"),
    )


def test_dashboard_returns_zero_kpis_for_empty_filter_result(db_session):
    dashboard = get_dashboard(db_session, DashboardFilters(region="不存在的区域"))

    assert dashboard.kpis.amount == Decimal("0")
    assert dashboard.kpis.quantity == 0
    assert dashboard.kpis.avg_order_value == Decimal("0")
    assert dashboard.kpis.profit_rate == Decimal("0")
    assert dashboard.deltas.amount == Decimal("0")
    assert dashboard.trend == []
    assert dashboard.regions == []
    assert dashboard.products == []


def test_anomalies_include_the_exact_eighteen_percent_boundary(db_session):
    db_session.add_all(
        [
            _order("BOUNDARY-202502", date(2025, 2, 1), Decimal("100"), "阈值区域"),
            _order("BOUNDARY-202503", date(2025, 3, 1), Decimal("118"), "阈值区域"),
        ]
    )
    db_session.commit()

    anomalies = detect_anomalies(db_session, as_of=date(2025, 4, 15))

    assert len(anomalies.items) == 1
    anomaly = anomalies.items[0]
    assert anomaly.region == "阈值区域"
    assert anomaly.previous_value == Decimal("100")
    assert anomaly.current_value == Decimal("118")
    assert anomaly.delta == Decimal("0.18")


def test_anomalies_default_to_the_latest_completed_data_month(db_session):
    db_session.add_all(
        [
            _order("ANCHORED-202001", date(2020, 1, 15), Decimal("100"), "数据锚点区域"),
            _order("ANCHORED-202002", date(2020, 2, 15), Decimal("125"), "数据锚点区域"),
        ]
    )
    db_session.commit()

    anomalies = detect_anomalies(db_session)

    assert len(anomalies.items) == 1
    anomaly = anomalies.items[0]
    assert anomaly.previous_value == Decimal("100")
    assert anomaly.current_value == Decimal("125")
    assert "2020-02" in anomaly.evidence
    assert "2020-01" in anomaly.evidence


def test_anomalies_exclude_partial_months_and_do_not_compare_across_gaps(db_session):
    db_session.add_all(
        [
            _order("GAP-202501", date(2025, 1, 1), Decimal("100"), "连续区域"),
            _order("GAP-202503", date(2025, 3, 1), Decimal("200"), "连续区域"),
            _order("GAP-202504", date(2025, 4, 1), Decimal("10000"), "连续区域"),
        ]
    )
    db_session.commit()

    as_of = date(2025, 4, 15)
    assert detect_anomalies(db_session, as_of=as_of).items == []

    db_session.add(_order("GAP-202502", date(2025, 2, 1), Decimal("100"), "连续区域"))
    db_session.commit()

    anomalies = detect_anomalies(db_session, as_of=as_of)

    assert len(anomalies.items) == 1
    anomaly = anomalies.items[0]
    assert anomaly.previous_value == Decimal("100")
    assert anomaly.current_value == Decimal("200")
    assert "2025-03" in anomaly.evidence
    assert "2025-02" in anomaly.evidence
    assert "2025-04" not in anomaly.evidence


def test_forecast_uses_deterministic_ols_prediction_and_month_label(db_session):
    db_session.add_all(
        [
            _order("OLS-202501", date(2025, 1, 1), Decimal("100"), "预测区域"),
            _order("OLS-202502", date(2025, 2, 1), Decimal("200"), "预测区域"),
            _order("OLS-202503", date(2025, 3, 1), Decimal("300"), "预测区域"),
        ]
    )
    db_session.commit()

    forecast = forecast_next_month(db_session)

    assert forecast.prediction is not None
    assert forecast.prediction.month == date(2025, 4, 1)
    assert forecast.prediction.amount == Decimal("400.00")
    assert forecast.prediction.basis == (
        "使用3个种子月度销售额进行普通最小二乘（OLS）线性回归；斜率为100.00元/月。"
    )
