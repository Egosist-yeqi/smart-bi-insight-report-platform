from collections.abc import Callable
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.schemas import DashboardFilters
from app.analytics.service import detect_anomalies, forecast_next_month, get_dashboard
from app.core.errors import AppError
from app.reports.schemas import ReportRequest, ReportResult, ReportSection


REPORT_MODULES = ("overview", "region", "ranking", "anomaly", "forecast")
MODULE_TITLES = {
    "overview": "销售概览",
    "region": "区域分析",
    "ranking": "产品排行",
    "anomaly": "异常指标",
    "forecast": "趋势预测",
}
Narrative = Callable[[ReportSection], str | None]


class ReportModulesRequiredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="REPORT_MODULES_REQUIRED",
            message="请至少选择一个报告模块。",
            status_code=400,
        )


def generate_report(
    session: Session,
    request: ReportRequest,
    narrative: Narrative | None = None,
) -> ReportResult:
    selected_modules = _selected_modules(request.modules)
    if not selected_modules:
        raise ReportModulesRequiredError()

    dashboard = get_dashboard(session, DashboardFilters())
    period = _period(dashboard.trend)
    anomalies = detect_anomalies(session, as_of=_next_month(period)) if period else None
    forecast = forecast_next_month(session)
    sections = [
        _section(module, dashboard, anomalies, forecast)
        for module in selected_modules
    ]
    engine = "local"
    if narrative is not None:
        sections = [_with_narrative(section, narrative) for section in sections]
        engine = "ai"

    generated_at = datetime.now(timezone.utc)
    display_period = period.isoformat() if period else "暂无可用数据"
    title = f"{display_period} 智能 BI 经营分析{request.report_type}"
    return ReportResult(
        title=title,
        period=display_period,
        sections=sections,
        markdown=_markdown(title, display_period, sections, generated_at),
        engine=engine,
        generated_at=generated_at,
    )


def _selected_modules(modules: list[str]) -> list[str]:
    selected = set(modules)
    return [module for module in REPORT_MODULES if module in selected]


def _period(trend) -> date | None:
    return trend[-1].month if trend else None


def _next_month(month: date) -> date:
    return date(month.year + (month.month == 12), month.month % 12 + 1, 1)


def _section(module, dashboard, anomalies, forecast) -> ReportSection:
    builders = {
        "overview": lambda: _overview(dashboard),
        "region": lambda: _region(dashboard),
        "ranking": lambda: _ranking(dashboard),
        "anomaly": lambda: _anomaly(anomalies),
        "forecast": lambda: _forecast(forecast),
    }
    return ReportSection(
        id=module,
        title=MODULE_TITLES[module],
        content=builders[module](),
    )


def _overview(dashboard) -> str:
    if not dashboard.trend:
        return "当前数据集为空；暂无可用销售数据。"
    latest = dashboard.trend[-1]
    return (
        f"{latest.month:%Y-%m}销售额{_currency(latest.amount)}，"
        f"销售数量{latest.quantity:,}。累计销售额{_currency(dashboard.kpis.amount)}，"
        f"累计毛利率{dashboard.kpis.profit_rate:.2%}。"
    )


def _region(dashboard) -> str:
    if not dashboard.regions:
        return "当前数据集为空；暂无可用区域销售数据。"
    top_region = dashboard.regions[0]
    return (
        f"{top_region.name}是当前销售额最高区域，销售额{_currency(top_region.amount)}，"
        f"订单量{top_region.order_count:,}，毛利率{top_region.profit_rate:.2%}。"
    )


def _ranking(dashboard) -> str:
    if not dashboard.products:
        return "当前数据集为空；暂无可用产品排行数据。"
    top_product = dashboard.products[0]
    return (
        f"销售额最高产品为{top_product.name}，销售额{_currency(top_product.amount)}，"
        f"销售数量{top_product.quantity:,}。"
    )


def _anomaly(anomalies) -> str:
    if anomalies is None or not anomalies.items:
        return "本周期未发现超过阈值的显著异常波动。"
    return "；".join(
        f"{item.region}{item.metric}{item.delta:+.2%}：{item.evidence}"
        for item in anomalies.items
    )


def _forecast(forecast) -> str:
    if forecast.prediction is None:
        return "历史数据不足，无法生成下月销售额预测。"
    prediction = forecast.prediction
    return (
        f"预计{prediction.month:%Y-%m}销售额约{_currency(prediction.amount)}。"
        f"{prediction.basis}预测仅供经营分析参考。"
    )


def _with_narrative(section: ReportSection, narrative: Narrative) -> ReportSection:
    try:
        addition = narrative(section)
    except Exception:
        return section
    if not addition or not addition.strip():
        return section
    return section.model_copy(update={"content": f"{section.content}\n\n{addition.strip()}"})


def _markdown(
    title: str,
    period: str,
    sections: list[ReportSection],
    generated_at: datetime,
) -> str:
    lines = [
        f"# {title}",
        "",
        f"统计周期：{period}",
        f"生成时间：{_timestamp(generated_at)}",
        "",
    ]
    for section in sections:
        lines.extend((f"## {section.title}", "", section.content, ""))
    lines.extend(
        (
            "## 说明",
            "",
            "本报告由业务数据和本地规则生成，预测与归因结果仅供经营分析参考。",
        )
    )
    return "\n".join(lines)


def _currency(value: Decimal) -> str:
    return f"{value:,.2f}元"


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
