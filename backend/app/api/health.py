from fastapi import APIRouter, Request
from sqlalchemy import func, select, text

from app.db.models import SalesOrder
from app.db.session import get_session

router = APIRouter()


def database_status() -> str:
    session_iterator = get_session()
    session = next(session_iterator)
    try:
        session.execute(text("SELECT 1"))
        return "up"
    except Exception:
        return "down"
    finally:
        session_iterator.close()


def seeded_order_count() -> int:
    session_iterator = get_session()
    session = next(session_iterator)
    try:
        return session.scalar(select(func.count()).select_from(SalesOrder)) or 0
    except Exception:
        return 0
    finally:
        session_iterator.close()


@router.get("/api/health")
def health(request: Request) -> dict:
    return {
        "data": {
            "app": "up",
            "database": database_status(),
            "seeded_orders": seeded_order_count(),
            "ai_mode": "local",
        },
        "request_id": request.state.request_id,
    }
