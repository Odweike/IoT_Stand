import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    safety_port: str = os.getenv("SAFETY_PORT", "/dev/ttyACM0")
    student_port: str = os.getenv("STUDENT_PORT", "/dev/ttyACM1")
    baudrate: int = int(os.getenv("BAUDRATE", "115200"))
    sim_mode: bool = _env_bool("SIM_MODE", True)
    arduino_cli_path: str = os.getenv("ARDUINO_CLI_PATH", "arduino-cli")
    upload_enabled: bool = _env_bool("UPLOAD_ENABLED", True)
    data_dir: str = os.getenv("DATA_DIR", "/data")
    baseline_fqbn: str = os.getenv("BASELINE_FQBN", "arduino:avr:uno")
    baseline_sketch_main: str | None = os.getenv("BASELINE_SKETCH_MAIN")


settings = Settings()
