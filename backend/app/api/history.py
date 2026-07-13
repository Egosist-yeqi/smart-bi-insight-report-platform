from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import QueryHistory
from app.db.session import get_session

router = APIRouter()


@router.get("/api/query-history")
def query_history(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_session),
) -> dict:
    records = session.scalars(
        select(QueryHistory)
        .order_by(QueryHistory.created_at.desc(), QueryHistory.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return {
        "data": [
            {
                "id": record.id,
                "question": record.question,
                "engine": record.engine,
                "summary": record.summary,
                "status": record.status,
                "error_code": record.error_code,
                "duration_ms": record.duration_ms,
                "created_at": record.created_at.isoformat(),
            }
            for record in records
        ],
        "request_id": request.state.request_id,
    }
