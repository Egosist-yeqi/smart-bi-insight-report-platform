from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.reports.schemas import ReportRequest
from app.reports.service import generate_report

router = APIRouter()


@router.post("/api/reports/generate")
def generate(
    payload: ReportRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    result = generate_report(session, payload)
    return {
        "data": result.model_dump(mode="json"),
        "request_id": request.state.request_id,
    }
