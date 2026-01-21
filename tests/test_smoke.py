from pathlib import Path

from fastapi.testclient import TestClient


def test_health_and_ui(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SIM_MODE", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ARDUINO_CLI_PATH", "/bin/true")
    monkeypatch.setenv("UPLOAD_ENABLED", "false")
    from app.main import app

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/ui/teacher").status_code == 200
        assert client.get("/ui/student").status_code == 200


def test_teacher_and_student_actions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SIM_MODE", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ARDUINO_CLI_PATH", "/bin/true")
    monkeypatch.setenv("UPLOAD_ENABLED", "false")
    from app.main import app

    with TestClient(app) as client:
        assert client.post("/api/teacher/drain_valve", json={"open": True}).status_code == 200
        assert client.post("/api/teacher/heater/stop").status_code == 200
        payload = {"pump": 100, "fan": [10, 20, 30]}
        assert client.post("/api/teacher/actuators", json=payload).status_code == 200

        mode_resp = client.post("/api/teacher/student_mode", json={"mode": "student"})
        assert mode_resp.status_code == 200
        blocked = client.post("/api/teacher/actuators", json=payload)
        assert blocked.status_code == 409

        files = {"file": ("sketch.ino", b"void setup(){}", "text/plain")}
        form = {"board_fqbn": "arduino:avr:uno"}
        upload_resp = client.post("/api/student/firmware/upload", data=form, files=files)
        assert upload_resp.status_code == 200

        back_resp = client.post("/api/teacher/student_mode", json={"mode": "baseline"})
        assert back_resp.status_code == 200
        upload_blocked = client.post("/api/student/firmware/upload", data=form, files=files)
        assert upload_blocked.status_code == 409


def test_ws_telemetry_includes_t3(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SIM_MODE", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ARDUINO_CLI_PATH", "/bin/true")
    monkeypatch.setenv("UPLOAD_ENABLED", "false")
    from app.main import app

    with TestClient(app) as client:
        with client.websocket_connect("/ws/telemetry") as ws:
            payload = ws.receive_json()
            assert "t3" in payload
