from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from html import escape as html_escape
import re
from unicodedata import normalize

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.service import detect_anomalies, forecast_next_month
from app.core.errors import AppError
from app.core.warnings import ServiceWarning, ai_service_warning
from app.db.models import SalesOrder
from app.reports.schemas import ReportRequest, ReportResult, ReportSection


ZERO = Decimal("0")
REPORT_MODULES = ("overview", "region", "ranking", "anomaly", "forecast")
MODULE_TITLES = {
    "overview": "销售概览",
    "region": "区域分析",
    "ranking": "产品排行",
    "anomaly": "异常指标",
    "forecast": "趋势预测",
}
MARKDOWN_ESCAPES = str.maketrans(
    {
        "\\": "\\\\",
        "`": "\\`",
        "*": "\\*",
        "_": "\\_",
        "{": "\\{",
        "}": "\\}",
        "[": "\\[",
        "]": "\\]",
        "(": "\\(",
        ")": "\\)",
        "#": "\\#",
        "+": "\\+",
        "-": "\\-",
        ".": "\\.",
        "!": "\\!",
        "|": "\\|",
        "~": "\\~",
    }
)
Narrative = Callable[[ReportSection], str | None]


@dataclass(frozen=True)
class _ReportPeriod:
    start: date | None
    end: date | None
    policy: str

    @property
    def label(self) -> str:
        if self.start is None or self.end is None:
            return "暂无可用数据"
        return f"{self.start.isoformat()}/{self.end.isoformat()}"


@dataclass(frozen=True)
class _PeriodMetrics:
    amount: Decimal
    quantity: int
    profit_rate: Decimal


@dataclass(frozen=True)
class _Ranking:
    name: str
    amount: Decimal
    quantity: int
    order_count: int
    profit_rate: Decimal


@dataclass(frozen=True)
class _ReportData:
    period: _ReportPeriod
    metrics: _PeriodMetrics
    regions: list[_Ranking]
    products: list[_Ranking]


@dataclass(frozen=True)
class _CompletedDataMonthPolicy:
    first_month: date | None
    latest_month: date | None
    data_as_of: date | None
    note: str


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

    report_data = _report_data(session, request.report_type)
    completed_month_policy = _completed_data_month_policy(session)
    anomalies = (
        detect_anomalies(
            session, today=_next_month(completed_month_policy.latest_month)
        )
        if completed_month_policy.latest_month
        else None
    )
    forecast = (
        forecast_next_month(session, through_month=completed_month_policy.latest_month)
        if completed_month_policy.latest_month
        else None
    )
    sections = [
        _section(module, report_data, completed_month_policy, anomalies, forecast)
        for module in selected_modules
    ]
    warning: ServiceWarning | None = None
    if narrative is None:
        from app.ai.service import get_report_narrative

        try:
            narrative = get_report_narrative(session)
        except AppError as exc:
            warning = report_fallback_warning(exc)
    sections, narrative_count, narrative_error = _add_narratives(sections, narrative)
    if narrative_error is not None and warning is None:
        warning = report_fallback_warning(narrative_error)
    engine = "ai" if narrative_count else "local"
    if narrative_count:
        provenance = (
            "ai_assisted"
            if narrative_count == len(sections) and warning is None
            else "ai_partial"
        )
    else:
        provenance = "local_fallback" if warning else "local"

    generated_at = datetime.now(timezone.utc)
    title = f"{report_data.period.label} 智能 BI 经营分析{request.report_type}"
    return ReportResult(
        title=title,
        period=report_data.period.label,
        sections=sections,
        markdown=_markdown(
            title,
            report_data.period,
            sections,
            provenance,
            generated_at,
        ),
        engine=engine,
        provenance=provenance,
        warning=warning,
        generated_at=generated_at,
    )


def report_fallback_warning(error: Exception) -> ServiceWarning:
    return ai_service_warning(
        error,
        message="AI 叙述服务不可用，已保留本地报告内容。",
        default_code="AI_NARRATIVE_FAILED",
    )


def _selected_modules(modules: list[str]) -> list[str]:
    selected = set(modules)
    return [module for module in REPORT_MODULES if module in selected]


def _report_data(session: Session, report_type: str) -> _ReportData:
    period = _period_for(session, report_type)
    predicates = _period_predicates(period)
    return _ReportData(
        period=period,
        metrics=_metrics(session, predicates),
        regions=_ranking(session, predicates, SalesOrder.region, SalesOrder.region),
        products=_ranking(
            session,
            predicates,
            SalesOrder.product_name,
            SalesOrder.product_id,
            SalesOrder.product_name,
        ),
    )


def _period_for(session: Session, report_type: str) -> _ReportPeriod:
    first_order, latest_order = session.execute(
        select(func.min(SalesOrder.order_date), func.max(SalesOrder.order_date))
    ).one()
    if latest_order is None:
        return _ReportPeriod(None, None, "当前数据集为空。")
    if report_type == "周报":
        start = latest_order - timedelta(days=6)
        return _ReportPeriod(start, latest_order, "最新数据锚定的连续7日。")
    if report_type == "月报":
        return _ReportPeriod(
            date(latest_order.year, latest_order.month, 1),
            latest_order,
            "最新数据月，自月初统计至数据锚点。",
        )
    return _ReportPeriod(first_order, latest_order, "自定义报告当前支持全量可用数据范围。")


def _completed_data_month_policy(
    session: Session, *, today: date | None = None
) -> _CompletedDataMonthPolicy:
    first_order, data_as_of = session.execute(
        select(func.min(SalesOrder.order_date), func.max(SalesOrder.order_date))
    ).one()
    if data_as_of is None:
        return _CompletedDataMonthPolicy(None, None, None, "当前数据集为空。")

    current_month = _month_start(today or date.today())
    latest_data_month = _month_start(data_as_of)
    maximum_completed_month = (
        _previous_month(current_month)
        if latest_data_month >= current_month
        else latest_data_month
    )
    first_month, completed_as_of = session.execute(
        select(func.min(SalesOrder.order_date), func.max(SalesOrder.order_date)).where(
            SalesOrder.order_date < _next_month(maximum_completed_month)
        )
    ).one()
    if completed_as_of is None:
        return _CompletedDataMonthPolicy(
            None,
            None,
            data_as_of,
            f"数据锚点{data_as_of.isoformat()}位于未完成的当前数据月，暂无可用完成数据月。",
        )

    completed_month = _month_start(completed_as_of)
    if latest_data_month >= current_month:
        note = (
            f"数据锚点{data_as_of.isoformat()}位于当前自然月，"
            f"已排除未完成的{latest_data_month:%Y-%m}。"
        )
    else:
        note = (
            f"数据锚点{data_as_of.isoformat()}为历史数据快照，"
            f"将{completed_month:%Y-%m}视为完成数据月。"
        )
    return _CompletedDataMonthPolicy(
        _month_start(first_month), completed_month, data_as_of, note
    )


def _period_predicates(period: _ReportPeriod) -> list:
    if period.start is None or period.end is None:
        return [SalesOrder.id.is_(None)]
    return [SalesOrder.order_date >= period.start, SalesOrder.order_date <= period.end]


def _metrics(session: Session, predicates: list) -> _PeriodMetrics:
    amount = func.coalesce(func.sum(SalesOrder.amount), ZERO)
    profit = func.coalesce(func.sum(SalesOrder.profit), ZERO)
    row = session.execute(
        select(
            amount.label("amount"),
            func.coalesce(func.sum(SalesOrder.quantity), 0).label("quantity"),
            profit.label("profit"),
        ).where(*predicates)
    ).one()
    amount_value = _decimal(row.amount)
    profit_value = _decimal(row.profit)
    return _PeriodMetrics(
        amount=amount_value,
        quantity=int(row.quantity or 0),
        profit_rate=profit_value / amount_value if amount_value else ZERO,
    )


def _ranking(session: Session, predicates: list, dimension, *group_by) -> list[_Ranking]:
    amount = func.coalesce(func.sum(SalesOrder.amount), ZERO)
    profit = func.coalesce(func.sum(SalesOrder.profit), ZERO)
    rows = session.execute(
        select(
            dimension.label("name"),
            amount.label("amount"),
            func.coalesce(func.sum(SalesOrder.quantity), 0).label("quantity"),
            profit.label("profit"),
            func.count(SalesOrder.id).label("order_count"),
        )
        .where(*predicates)
        .group_by(*group_by)
        .order_by(amount.desc(), dimension.asc())
    )
    return [
        _Ranking(
            name=str(row.name),
            amount=_decimal(row.amount),
            quantity=int(row.quantity or 0),
            order_count=int(row.order_count or 0),
            profit_rate=_decimal(row.profit) / _decimal(row.amount)
            if _decimal(row.amount)
            else ZERO,
        )
        for row in rows
    ]


def _decimal(value: Decimal | int | None) -> Decimal:
    return Decimal(value or ZERO)


def _next_month(month: date) -> date:
    return date(month.year + (month.month == 12), month.month % 12 + 1, 1)


def _previous_month(month: date) -> date:
    return date(month.year - (month.month == 1), (month.month - 2) % 12 + 1, 1)


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _section(
    module,
    report_data,
    completed_month_policy,
    anomalies,
    forecast,
) -> ReportSection:
    builders = {
        "overview": lambda: _overview(report_data),
        "region": lambda: _region(report_data),
        "ranking": lambda: _ranking_section(report_data),
        "anomaly": lambda: _anomaly(anomalies, completed_month_policy),
        "forecast": lambda: _forecast(forecast, completed_month_policy),
    }
    return ReportSection(
        id=module,
        title=MODULE_TITLES[module],
        content=builders[module](),
    )


def _overview(report_data: _ReportData) -> str:
    if report_data.period.end is None:
        return "当前数据集为空；暂无可用销售数据。"
    metrics = report_data.metrics
    return (
        f"统计周期{report_data.period.label}销售额{_currency(metrics.amount)}，"
        f"销售数量{metrics.quantity:,}，毛利率{metrics.profit_rate:.2%}。"
    )


def _region(report_data: _ReportData) -> str:
    if not report_data.regions:
        return "当前报告周期暂无可用区域销售数据。"
    top_region = report_data.regions[0]
    return (
        f"{_safe_inline(top_region.name)}是统计周期内销售额最高区域，"
        f"销售额{_currency(top_region.amount)}，订单量{top_region.order_count:,}，"
        f"毛利率{top_region.profit_rate:.2%}。"
    )


def _ranking_section(report_data: _ReportData) -> str:
    if not report_data.products:
        return "当前报告周期暂无可用产品排行数据。"
    top_product = report_data.products[0]
    return (
        f"统计周期内销售额最高产品为{_safe_inline(top_product.name)}，"
        f"销售额{_currency(top_product.amount)}，销售数量{top_product.quantity:,}。"
    )


def _anomaly(anomalies, policy: _CompletedDataMonthPolicy) -> str:
    if policy.latest_month is None:
        return f"完成数据月口径：{policy.note}无法生成异常参考。"
    previous_month = _previous_month(policy.latest_month)
    reference = (
        f"异常参考：完成数据月{policy.latest_month:%Y-%m}，"
        f"与相邻上月{previous_month:%Y-%m}的月度区域销售额对比。{policy.note}"
    )
    if anomalies is None or not anomalies.items:
        return f"{reference}本参考周期未发现超过阈值的显著异常波动。"
    details = "；".join(
        _safe_inline(f"{item.region}{item.metric}{item.delta:+.2%}：{item.evidence}")
        for item in anomalies.items
    )
    return f"{reference}{details}"


def _forecast(forecast, policy: _CompletedDataMonthPolicy) -> str:
    if policy.latest_month is None or policy.first_month is None:
        return f"完成数据月口径：{policy.note}历史数据不足，无法生成下月销售额预测。"
    reference = (
        f"预测参考：完成数据月截至{policy.latest_month:%Y-%m}，"
        f"使用{policy.first_month:%Y-%m}至{policy.latest_month:%Y-%m}的月度历史数据。"
        f"{policy.note}"
    )
    if forecast is None or forecast.prediction is None:
        return f"{reference}历史数据不足，无法生成下月销售额预测。"
    prediction = forecast.prediction
    return (
        f"{reference}预计{prediction.month:%Y-%m}销售额约{_currency(prediction.amount)}。"
        f"{prediction.basis}预测仅供经营分析参考。"
    )


def _add_narratives(
    sections: list[ReportSection], narrative: Narrative | None
) -> tuple[list[ReportSection], int, Exception | None]:
    if narrative is None:
        return sections, 0, None
    results = [_with_narrative(section, narrative) for section in sections]
    first_error = next((error for _, _, error in results if error is not None), None)
    return (
        [section for section, _, _ in results],
        sum(applied for _, applied, _ in results),
        first_error,
    )


def _with_narrative(
    section: ReportSection, narrative: Narrative
) -> tuple[ReportSection, bool, Exception | None]:
    try:
        addition = narrative(section)
    except Exception as exc:
        return section, False, exc
    if addition is None:
        return section, False, None
    if not isinstance(addition, str):
        return section, False, ValueError("invalid narrative type")
    safe_addition = _safe_paragraphs(addition)
    if not safe_addition:
        return section, False, ValueError("empty narrative")
    return (
        section.model_copy(update={"content": f"{section.content}\n\n{safe_addition}"}),
        True,
        None,
    )


def _safe_inline(value: str) -> str:
    return _escape_markdown(_collapse_whitespace(value))


def _safe_paragraphs(value: str) -> str:
    normalized = _normalize_text(value)
    paragraphs = [
        _escape_markdown(_collapse_whitespace(paragraph))
        for paragraph in re.split(r"\n\s*\n+", normalized)
    ]
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _normalize_text(value: str) -> str:
    normalized = normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")
    return "".join(character if character == "\n" or character >= " " else " " for character in normalized)


def _collapse_whitespace(value: str) -> str:
    return " ".join(_normalize_text(value).split())


def _escape_markdown(value: str) -> str:
    return html_escape(value, quote=False).translate(MARKDOWN_ESCAPES)


def _markdown(
    title: str,
    period: _ReportPeriod,
    sections: list[ReportSection],
    provenance: str,
    generated_at: datetime,
) -> str:
    lines = [
        f"# {title}",
        "",
        f"统计周期：{period.label}",
        f"统计口径：{period.policy}",
        f"生成时间：{_timestamp(generated_at)}",
        "",
    ]
    for section in sections:
        lines.extend((f"## {section.title}", "", section.content, ""))
    lines.extend(("## 说明", "", _source_label(provenance)))
    return "\n".join(lines)


def _source_label(provenance: str) -> str:
    if provenance == "ai_assisted":
        return (
            "数据来源：本地业务数据和本地规则；全部章节附加了 AI 叙述。"
            "预测与归因结果仅供经营分析参考。"
        )
    if provenance == "ai_partial":
        return (
            "数据来源：本地业务数据和本地规则；部分章节附加了 AI 叙述，"
            "其余章节保留本地内容。预测与归因结果仅供经营分析参考。"
        )
    if provenance == "local_fallback":
        return (
            "数据来源：本地业务数据和本地规则。AI 叙述不可用，"
            "报告已由本地业务数据和本地规则生成。预测与归因结果仅供经营分析参考。"
        )
    return "数据来源：本地业务数据和本地规则。预测与归因结果仅供经营分析参考。"


def _currency(value: Decimal) -> str:
    return f"{value:,.2f}元"


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
