from fastapi import APIRouter, Request
from sqlalchemy import text

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
    return 0


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
