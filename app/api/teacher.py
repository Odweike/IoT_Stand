from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
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


class DrainValveRequest(BaseModel):
    open: bool


class StudentModeRequest(BaseModel):
    mode: str = Field(pattern="^(baseline|student)$")


class ActuatorRequest(BaseModel):
    pump: int = Field(ge=0, le=255)
    fan: list[int] = Field(min_length=3, max_length=3)


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


@router.post("/drain_valve")
async def drain_valve(payload: DrainValveRequest, request: Request) -> dict:
    simulator = request.app.state.simulator
    if simulator:
        simulator.set_drain_valve(payload.open)
    seq = request.app.state.safety_seq
    request.app.state.safety_seq += 1
    cmd = request.app.state.serial_safety.build_cmd(seq, {"drain_valve": 1 if payload.open else 0})
    await request.app.state.serial_safety.send_command(cmd)
    await request.app.state.db.insert_event("teacher", "drain_valve", payload.model_dump())
    return {"ok": True, "open": payload.open}


@router.post("/actuators")
async def set_actuators(payload: ActuatorRequest, request: Request) -> dict:
    if request.app.state.student_mode != "baseline":
        return JSONResponse(
            status_code=409,
            content={
                "ok": False,
                "error": "Student firmware mode enabled; web actuators disabled.",
            },
        )
    if any(v < 0 or v > 255 for v in payload.fan):
        raise HTTPException(status_code=400, detail="fan values out of range")
    simulator = request.app.state.simulator
    if simulator:
        simulator.set_actuators(payload.pump, payload.fan)
    seq = request.app.state.student_seq
    request.app.state.student_seq += 1
    cmd = request.app.state.serial_student.build_cmd(seq, {"pump": payload.pump, "fan": payload.fan})
    await request.app.state.serial_student.send_command(cmd)
    await request.app.state.db.insert_event("teacher", "actuators_set", payload.model_dump())
    return {"ok": True}


@router.get("/student_mode")
async def get_student_mode(request: Request) -> dict:
    return {"ok": True, "mode": request.app.state.student_mode}


@router.post("/student_mode")
async def set_student_mode(payload: StudentModeRequest, request: Request) -> dict:
    mode = payload.mode
    request.app.state.student_mode = mode
    warning = None
    result = None
    if mode == "baseline" and request.app.state.config.upload_enabled:
        result = await request.app.state.flashing.flash_baseline()
        if not result.ok:
            warning = result.message
    if mode == "student" and not request.app.state.config.upload_enabled:
        warning = "upload disabled by configuration"
    await request.app.state.db.insert_event("teacher", "student_mode", payload.model_dump())
    response = {"ok": True, "mode": mode}
    if warning:
        response["warning"] = warning
    if result:
        response["baseline_flash"] = {
            "ok": result.ok,
            "message": result.message,
            "compile": {"stdout": result.compile_stdout, "stderr": result.compile_stderr},
            "upload": {"stdout": result.upload_stdout, "stderr": result.upload_stderr},
        }
    return response
