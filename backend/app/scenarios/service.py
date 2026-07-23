import csv
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from io import StringIO

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import QueryHistory, SalesOrder, ScenarioState
from app.scenarios.catalog import CSV_HEADERS, SCENARIO_BY_ID, SCENARIOS, ScenarioDefinition


class ScenarioNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__("SCENARIO_NOT_FOUND", "未找到指定行业场景。", status_code=404)


class ScenarioImportError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("SCENARIO_IMPORT_INVALID", message, status_code=400)


def get_scenario_library(session: Session) -> dict:
    state = session.get(ScenarioState, 1)
    active_id = state.scenario_id if state else "ecommerce"
    data_source = state.data_source if state else "demo"
    return {
        "active_scenario_id": active_id,
        "data_source": data_source,
        "scenarios": [_scenario_payload(item, item.identifier == active_id) for item in SCENARIOS],
    }


def activate_demo_scenario(session: Session, scenario_id: str) -> dict:
    scenario = _scenario(scenario_id)
    _clear_dataset(session)
    session.add_all(_demo_orders(scenario))
    _set_state(session, scenario.identifier, "demo")
    session.commit()
    return {"scenario": _scenario_payload(scenario, True), "orders_loaded": 540, "data_source": "demo"}


def import_scenario_csv(session: Session, scenario_id: str, csv_text: str) -> dict:
    scenario = _scenario(scenario_id)
    orders = _parse_csv(scenario, csv_text)
    _clear_dataset(session)
    session.add_all(orders)
    _set_state(session, scenario.identifier, "imported")
    session.commit()
    return {"scenario": _scenario_payload(scenario, True), "rows_imported": len(orders), "data_source": "imported"}


def _scenario(identifier: str) -> ScenarioDefinition:
    scenario = SCENARIO_BY_ID.get(identifier)
    if scenario is None:
        raise ScenarioNotFoundError()
    return scenario


def _scenario_payload(scenario: ScenarioDefinition, active: bool) -> dict:
    return {
        "id": scenario.identifier,
        "title": scenario.title,
        "description": scenario.description,
        "entity_label": scenario.entity_label,
        "amount_label": scenario.amount_label,
        "quantity_label": scenario.quantity_label,
        "region_label": scenario.region_label,
        "category_label": scenario.category_label,
        "customer_label": scenario.customer_label,
        "active": active,
        "question_groups": [
            {"title": title, "questions": [question.text for question in questions]}
            for title, questions in scenario.question_groups
        ],
        "field_mappings": [{"field": field, "label": label} for field, label in scenario.field_mappings],
        "csv_headers": list(CSV_HEADERS),
        "sample_row": _sample_row(scenario),
    }


def _sample_row(scenario: ScenarioDefinition) -> dict[str, str]:
    item_id, item_name, category, _price, _margin, customer_type = scenario.items[0]
    region, province, _multiplier = scenario.regions[0]
    return {
        "record_id": "example-001",
        "date": "2026-06-01",
        "region": region,
        "province": province,
        "item_id": str(item_id),
        "item_name": item_name,
        "category": category,
        "customer_type": customer_type,
        "quantity": "100",
        "amount": "100000.00",
        "profit": "30000.00",
    }


def _demo_orders(scenario: ScenarioDefinition) -> list[SalesOrder]:
    orders: list[SalesOrder] = []
    for month_index in range(18):
        month_start = date(2025 + month_index // 12, month_index % 12 + 1, 1)
        season_factor = Decimal("1.00") + Decimal((month_index % 6) - 2) / Decimal("100")
        for region_index, (region, province, multiplier) in enumerate(scenario.regions):
            for item_id, name, category, unit_price, margin, customer_type in scenario.items:
                quantity = 20 + ((month_index + 1) * 7 + region_index * 11 + item_id * 13) % 181
                amount = (Decimal(quantity) * unit_price * multiplier * season_factor).quantize(Decimal("0.01"))
                orders.append(SalesOrder(
                    external_order_id=f"DEMO-{scenario.identifier}-{month_start:%Y%m}-{region_index}-{item_id}",
                    order_date=month_start + timedelta(days=(region_index * 5 + item_id * 3) % 27),
                    region=region,
                    province=province,
                    product_id=item_id,
                    product_name=name,
                    category=category,
                    customer_type=customer_type,
                    quantity=quantity,
                    amount=amount,
                    profit=(amount * margin).quantize(Decimal("0.01")),
                ))
    return orders


def _parse_csv(scenario: ScenarioDefinition, csv_text: str) -> list[SalesOrder]:
    reader = csv.DictReader(StringIO(csv_text.lstrip("\ufeff")))
    if reader.fieldnames is None or tuple(reader.fieldnames) != CSV_HEADERS:
        raise ScenarioImportError("CSV 列必须严格匹配场景模板的 11 个字段及其顺序。")
    rows = list(reader)
    if not rows:
        raise ScenarioImportError("CSV 不包含可导入的数据行。")
    if len(rows) > 10_000:
        raise ScenarioImportError("单次最多导入 10000 行数据。")
    orders: list[SalesOrder] = []
    record_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        try:
            record_id = _text(row["record_id"], 16)
            if record_id in record_ids:
                raise ValueError("record_id 重复")
            record_ids.add(record_id)
            order_date = date.fromisoformat(_text(row["date"], 10))
            product_id = int(_text(row["item_id"], 18))
            quantity = int(_text(row["quantity"], 12))
            amount = Decimal(_text(row["amount"], 30))
            profit = Decimal(_text(row["profit"], 30))
            if product_id < 0 or quantity < 0 or amount < 0 or profit < 0:
                raise ValueError("数值不能为负")
            orders.append(SalesOrder(
                external_order_id=f"IMPORT-{scenario.identifier}-{record_id}",
                order_date=order_date,
                region=_text(row["region"], 20),
                province=_text(row["province"], 40),
                product_id=product_id,
                product_name=_text(row["item_name"], 120),
                category=_text(row["category"], 40),
                customer_type=_text(row["customer_type"], 40),
                quantity=quantity,
                amount=amount.quantize(Decimal("0.01")),
                profit=profit.quantize(Decimal("0.01")),
            ))
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise ScenarioImportError(f"第 {row_number} 行无效：{exc}。") from exc
    return orders


def _text(value: str | None, max_length: int) -> str:
    text = (value or "").strip()
    if not text or len(text) > max_length:
        raise ValueError("字段为空或超出长度限制")
    return text


def _clear_dataset(session: Session) -> None:
    session.execute(delete(SalesOrder))
    session.execute(delete(QueryHistory))


def _set_state(session: Session, scenario_id: str, data_source: str) -> None:
    state = session.get(ScenarioState, 1)
    if state is None:
        session.add(ScenarioState(id=1, scenario_id=scenario_id, data_source=data_source))
    else:
        state.scenario_id = scenario_id
        state.data_source = data_source
