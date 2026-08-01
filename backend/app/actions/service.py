from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.schemas import ActionCreate, ActionItem, ActionListResult, ActionSummary, ActionUpdate
from app.core.errors import AppError
from app.db.models import DecisionAction


def list_actions(session: Session) -> ActionListResult:
    items = list(
        session.scalars(
            select(DecisionAction).order_by(
                DecisionAction.status.asc(),
                DecisionAction.priority.asc(),
                DecisionAction.due_date.is_(None),
                DecisionAction.due_date.asc(),
                DecisionAction.id.desc(),
            )
        )
    )
    statuses = {status: 0 for status in ("open", "in_progress", "completed")}
    for item in items:
        statuses[item.status] += 1
    overdue = sum(
        1
        for item in items
        if item.status != "completed" and item.due_date is not None and item.due_date < date.today()
    )
    return ActionListResult(
        items=[_item_payload(item) for item in items],
        summary=ActionSummary(**statuses, overdue=overdue),
    )


def create_action(session: Session, payload: ActionCreate) -> ActionItem:
    action = DecisionAction(status="open", **payload.model_dump())
    session.add(action)
    session.commit()
    session.refresh(action)
    return _item_payload(action)


def update_action(session: Session, action_id: int, payload: ActionUpdate) -> ActionItem:
    action = session.get(DecisionAction, action_id)
    if action is None:
        raise AppError("ACTION_NOT_FOUND", "未找到指定行动项。", status_code=404)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("status") == "completed" and not (changes.get("review_notes") or action.review_notes):
        raise AppError("ACTION_REVIEW_REQUIRED", "完成行动前请填写复盘结论。", status_code=400)
    for field, value in changes.items():
        setattr(action, field, value)
    session.commit()
    session.refresh(action)
    return _item_payload(action)


def _item_payload(action: DecisionAction) -> ActionItem:
    return ActionItem(
        id=action.id,
        title=action.title,
        owner=action.owner,
        priority=action.priority,
        status=action.status,
        due_date=action.due_date,
        target_metric=action.target_metric,
        source_type=action.source_type,
        evidence=action.evidence,
        review_notes=action.review_notes,
        created_at=action.created_at,
        updated_at=action.updated_at,
    )
