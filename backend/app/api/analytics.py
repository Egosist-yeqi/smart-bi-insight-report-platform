from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.analytics.service import detect_anomalies, forecast_next_month
from app.db.session import get_session

router = APIRouter()


@router.get("/api/anomalies")
def anomalies(request: Request, session: Session = Depends(get_session)) -> dict:
    result = detect_anomalies(session)
    return {
        "data": result.model_dump(mode="json"),
        "request_id": request.state.request_id,
    }


@router.get("/api/forecast")
def forecast(request: Request, session: Session = Depends(get_session)) -> dict:
    result = forecast_next_month(session)
    return {
        "data": result.model_dump(mode="json"),
        "request_id": request.state.request_id,
    }
