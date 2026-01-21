import asyncio
import json
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import health, student, teacher
from app.config import settings
from app.services.db import get_db
from app.services.flashing_service import FlashingService
from app.services.scenario_engine import ScenarioEngine
from app.services.serial_manager import SerialConfig, SerialManager
from app.services.telemetry_service import TelemetryService, TelemetrySimulator

app = FastAPI(title="Lab Stand Controller")

app.include_router(health.router)
app.include_router(teacher.router)
app.include_router(student.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


@app.get("/ui/teacher", response_class=HTMLResponse)
async def teacher_ui(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("teacher.html", {"request": request})


@app.get("/ui/student", response_class=HTMLResponse)
async def student_ui(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("student.html", {"request": request})


@app.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket) -> None:
    await app.state.telemetry.register(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await app.state.telemetry.unregister(websocket)


async def _on_serial_message(payload: Dict[str, Any], source_device: str) -> None:
    if payload.get("type") == "telemetry":
        await app.state.telemetry.update(payload, source_device)
    elif payload.get("type") in {"fault", "ack"}:
        await app.state.db.insert_event("system", payload.get("type", "serial"), payload)


@app.on_event("startup")
async def startup() -> None:
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    db = get_db(str(data_dir / "db.sqlite"))
    telemetry = TelemetryService(db)

    safety_serial = SerialManager(
        SerialConfig(port=settings.safety_port, baudrate=settings.baudrate, name="safety"),
        _on_serial_message,
        sim_mode=settings.sim_mode,
    )
    student_serial = SerialManager(
        SerialConfig(port=settings.student_port, baudrate=settings.baudrate, name="student"),
        _on_serial_message,
        sim_mode=settings.sim_mode,
    )

    simulator = TelemetrySimulator(telemetry) if settings.sim_mode else None

    app.state.db = db
    app.state.telemetry = telemetry
    app.state.serial_safety = safety_serial
    app.state.serial_student = student_serial
    app.state.simulator = simulator
    app.state.scenario_engine = ScenarioEngine(safety_serial, simulator)
    app.state.flashing = FlashingService()
    app.state.student_seq = 1
    app.state.safety_seq = 1
    app.state.student_mode = "baseline"
    app.state.config = settings

    await safety_serial.start()
    await student_serial.start()
    if simulator:
        await simulator.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await app.state.serial_safety.stop()
    await app.state.serial_student.stop()
