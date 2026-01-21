import os
from pathlib import Path

from fastapi.testclient import TestClient


def test_health_and_ui(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SIM_MODE", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.main import app

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/ui/teacher").status_code == 200
        assert client.get("/ui/student").status_code == 200


def test_teacher_and_student_actions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SIM_MODE", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.main import app

    with TestClient(app) as client:
        assert client.post("/api/teacher/heater/stop").status_code == 200
        payload = {"pump": 100, "fan": [10, 20, 30]}
        assert client.post("/api/student/actuators", json=payload).status_code == 200
