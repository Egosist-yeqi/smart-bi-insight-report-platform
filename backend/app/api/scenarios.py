from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.scenarios.schemas import ScenarioImportInput
from app.scenarios.service import activate_demo_scenario, get_scenario_library, import_scenario_csv


router = APIRouter()


@router.get("/api/scenarios")
def scenarios(request: Request, session: Session = Depends(get_session)) -> dict:
    return {"data": get_scenario_library(session), "request_id": request.state.request_id}


@router.post("/api/scenarios/{scenario_id}/activate")
def activate_scenario(scenario_id: str, request: Request, session: Session = Depends(get_session)) -> dict:
    return {"data": activate_demo_scenario(session, scenario_id), "request_id": request.state.request_id}


@router.post("/api/scenarios/import")
def import_scenario(payload: ScenarioImportInput, request: Request, session: Session = Depends(get_session)) -> dict:
    return {"data": import_scenario_csv(session, payload.scenario_id, payload.csv_text), "request_id": request.state.request_id}
