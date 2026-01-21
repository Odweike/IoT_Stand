import time
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.services.serial_manager import SerialManager

router = APIRouter(prefix="/api/student", tags=["student"])


class ActuatorRequest(BaseModel):
    pump: int = Field(ge=0, le=255)
    fan: List[int] = Field(min_length=3, max_length=3)


@router.post("/actuators")
async def set_actuators(payload: ActuatorRequest, request: Request) -> dict:
    if request.app.state.student_mode != "baseline":
        return JSONResponse(
            status_code=409,
            content={
                "ok": False,
                "error": "Student firmware mode enabled by teacher; web actuators disabled.",
            },
        )
    if any(v < 0 or v > 255 for v in payload.fan):
        raise HTTPException(status_code=400, detail="fan values out of range")
    simulator = request.app.state.simulator
    if simulator:
        simulator.set_actuators(payload.pump, payload.fan)
    seq = request.app.state.student_seq
    request.app.state.student_seq += 1
    cmd = SerialManager.build_cmd(seq, {"pump": payload.pump, "fan": payload.fan})
    await request.app.state.serial_student.send_command(cmd)
    await request.app.state.db.insert_event("student", "actuators", payload.model_dump())
    return {"ok": True}


@router.post("/firmware/upload")
async def firmware_upload(
    request: Request,
    file: UploadFile = File(...),
    board_fqbn: str = Form(...),
    sketch_main: Optional[str] = Form(None),
) -> dict:
    if request.app.state.student_mode != "student":
        return JSONResponse(
            status_code=409,
            content={
                "ok": False,
                "error": "Firmware upload disabled; teacher must enable student mode.",
            },
        )
    if file.filename is None:
        raise HTTPException(status_code=400, detail="missing file")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".zip", ".ino"}:
        raise HTTPException(status_code=400, detail="file must be .zip or .ino")

    upload_dir = Path(settings.data_dir) / "uploads" / "student" / "incoming"
    upload_dir.mkdir(parents=True, exist_ok=True)
    temp_path = upload_dir / f"{int(time.time() * 1000)}_{file.filename}"
    with temp_path.open("wb") as handle:
        handle.write(await file.read())

    try:
        result = await request.app.state.flashing.flash_sketch(
            temp_path,
            board_fqbn=board_fqbn,
            sketch_main=sketch_main,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if temp_path.exists():
            temp_path.unlink()

    await request.app.state.db.insert_event(
        "student",
        "firmware_upload",
        {"board_fqbn": board_fqbn, "sketch_main": sketch_main},
    )

    return {
        "ok": result.ok,
        "message": result.message,
        "compile": {"stdout": result.compile_stdout, "stderr": result.compile_stderr},
        "upload": {"stdout": result.upload_stdout, "stderr": result.upload_stderr},
        "upload_enabled": settings.upload_enabled,
        "student_port": settings.student_port,
    }
