from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.ai.schemas import AIProviderInput, AIProviderTestPayload
from app.ai.service import delete_provider, get_provider_view, save_provider, test_provider
from app.db.session import get_session


router = APIRouter()


@router.get("/api/settings/ai")
def get_ai_settings(request: Request, session: Session = Depends(get_session)) -> dict:
    return {
        "data": get_provider_view(session).model_dump(),
        "request_id": request.state.request_id,
    }


@router.put("/api/settings/ai")
def put_ai_settings(
    payload: AIProviderInput,
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    return {
        "data": save_provider(session, payload).model_dump(),
        "request_id": request.state.request_id,
    }


@router.delete("/api/settings/ai")
def remove_ai_settings(request: Request, session: Session = Depends(get_session)) -> dict:
    return {
        "data": delete_provider(session).model_dump(exclude_none=True),
        "request_id": request.state.request_id,
    }


@router.post("/api/settings/ai/test")
def test_ai_settings(
    payload: AIProviderTestPayload,
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    return {
        "data": test_provider(session, payload).model_dump(),
        "request_id": request.state.request_id,
    }
