from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.ai.service import get_intent_resolver
from app.core.errors import AppError
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
    try:
        resolver = get_intent_resolver(session)
        fallback_notice = None
    except AppError:
        resolver = None
        fallback_notice = "AI 配置不可用，已使用本地规则解析。"
    result = run_query(
        session, payload.question, resolver=resolver, fallback_notice=fallback_notice
    )
    return {
        "data": result.model_dump(mode="json"),
        "request_id": request.state.request_id,
    }
