from fastapi import APIRouter, Request
from sqlalchemy import func, select, text

from app.core.errors import AppError
from app.db.models import AIProviderConfig, SalesOrder
from app.db.session import get_session

router = APIRouter()


def health_snapshot() -> dict:
    session_iterator = get_session()
    try:
        session = next(session_iterator)
        session.execute(text("SELECT 1"))
        seeded_orders = session.scalar(select(func.count()).select_from(SalesOrder)) or 0
        provider = session.scalar(
            select(AIProviderConfig.provider_name).where(
                AIProviderConfig.id == 1,
                AIProviderConfig.enabled.is_(True),
            )
        )
        return {
            "app": "up",
            "database": "up",
            "seeded_orders": seeded_orders,
            "ai_mode": "ai" if provider is not None else "local",
            "provider": provider,
        }
    except Exception:
        return {
            "app": "up",
            "database": "down",
            "seeded_orders": 0,
            "ai_mode": "local",
            "provider": None,
        }
    finally:
        session_iterator.close()


@router.get("/api/health")
def health(request: Request) -> dict:
    snapshot = health_snapshot()
    if snapshot["database"] != "up":
        raise AppError(
            code="DATABASE_UNAVAILABLE",
            message="数据库连接不可用。",
            status_code=503,
            details=snapshot,
        )
    return {
        "data": snapshot,
        "request_id": request.state.request_id,
    }
