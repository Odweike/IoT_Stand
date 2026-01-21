from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.scenario_engine import RandomScenarioConfig

router = APIRouter(prefix="/api/teacher", tags=["teacher"])


class ManualHeaterRequest(BaseModel):
    power: int = Field(ge=0, le=100)


class RandomHeaterRequest(BaseModel):
    min: int = Field(ge=0, le=100)
    max: int = Field(ge=0, le=100)
    on_min_s: int = Field(ge=1, le=3600)
    on_max_s: int = Field(ge=1, le=3600)
    off_min_s: int = Field(ge=1, le=3600)
    off_max_s: int = Field(ge=1, le=3600)


@router.post("/heater/manual")
async def heater_manual(payload: ManualHeaterRequest, request: Request) -> dict:
    engine = request.app.state.scenario_engine
    await engine.set_manual(payload.power)
    await request.app.state.db.insert_event("teacher", "heater_manual", payload.model_dump())
    return {"ok": True}


@router.post("/heater/random")
async def heater_random(payload: RandomHeaterRequest, request: Request) -> dict:
    if payload.min > payload.max:
        raise HTTPException(status_code=400, detail="min must be <= max")
    if payload.on_min_s > payload.on_max_s or payload.off_min_s > payload.off_max_s:
        raise HTTPException(status_code=400, detail="min duration must be <= max duration")
    engine = request.app.state.scenario_engine
    config = RandomScenarioConfig(
        min_power=payload.min,
        max_power=payload.max,
        on_min_s=payload.on_min_s,
        on_max_s=payload.on_max_s,
        off_min_s=payload.off_min_s,
        off_max_s=payload.off_max_s,
    )
    await engine.start_random(config)
    await request.app.state.db.insert_event("teacher", "heater_random", payload.model_dump())
    return {"ok": True}


@router.post("/heater/stop")
async def heater_stop(request: Request) -> dict:
    engine = request.app.state.scenario_engine
    await engine.stop()
    await request.app.state.db.insert_event("teacher", "heater_stop", {})
    return {"ok": True}
