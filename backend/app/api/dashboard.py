from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.analytics.schemas import DashboardFilters
from app.analytics.service import get_dashboard
from app.db.session import get_session

router = APIRouter()


@router.get("/api/dashboard")
def dashboard(
    request: Request,
    region: str | None = None,
    category: str | None = None,
    customer_type: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    result = get_dashboard(
        session,
        DashboardFilters(
            region=region,
            category=category,
            customer_type=customer_type,
        ),
    )
    return {
        "data": result.model_dump(mode="json"),
        "request_id": request.state.request_id,
    }
