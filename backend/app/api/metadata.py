from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.analytics.service import get_metadata
from app.db.session import get_session

router = APIRouter()


@router.get("/api/metadata")
def metadata(request: Request, session: Session = Depends(get_session)) -> dict:
    result = get_metadata(session)
    return {
        "data": result.model_dump(mode="json"),
        "request_id": request.state.request_id,
    }
