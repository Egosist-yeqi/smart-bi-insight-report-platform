from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.ai.service import get_intent_resolver
from app.db.session import get_session
from app.query.schemas import QueryRequest
from app.query.service import run_query

router = APIRouter()


@router.post("/api/query")
def query(
    payload: QueryRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    result = run_query(session, payload.question, resolver=get_intent_resolver(session))
    return {
        "data": result.model_dump(mode="json"),
        "request_id": request.state.request_id,
    }
