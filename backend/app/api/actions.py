from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.actions.schemas import ActionCreate, ActionUpdate
from app.actions.service import create_action, list_actions, update_action
from app.db.session import get_session


router = APIRouter()


@router.get("/api/actions")
def actions(request: Request, session: Session = Depends(get_session)) -> dict:
    return {"data": list_actions(session).model_dump(mode="json"), "request_id": request.state.request_id}


@router.post("/api/actions")
def create(payload: ActionCreate, request: Request, session: Session = Depends(get_session)) -> dict:
    return {"data": create_action(session, payload).model_dump(mode="json"), "request_id": request.state.request_id}


@router.patch("/api/actions/{action_id}")
def update(action_id: int, payload: ActionUpdate, request: Request, session: Session = Depends(get_session)) -> dict:
    return {"data": update_action(session, action_id, payload).model_dump(mode="json"), "request_id": request.state.request_id}
