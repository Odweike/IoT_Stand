import asyncio
import os
import shutil
import subprocess
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import settings


@dataclass
class FlashResult:
    ok: bool
    compile_stdout: str
    compile_stderr: str
    upload_stdout: str
    upload_stderr: str
    message: str


class FlashingService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def flash_sketch(
        self,
        file_path: Path,
        board_fqbn: str,
        sketch_main: Optional[str],
    ) -> FlashResult:
        async with self._lock:
            workdir = self._prepare_workspace(file_path)
            sketch_dir = self._resolve_sketch_dir(workdir, sketch_main)
            compile_cmd = [
                settings.arduino_cli_path,
                "compile",
                "--fqbn",
                board_fqbn,
                str(sketch_dir),
            ]
            compile_stdout, compile_stderr, compile_ok = await self._run_cmd(compile_cmd)
            if not compile_ok:
                return FlashResult(
                    ok=False,
                    compile_stdout=compile_stdout,
                    compile_stderr=compile_stderr,
                    upload_stdout="",
                    upload_stderr="",
                    message="compile failed",
                )
            if not settings.upload_enabled:
                return FlashResult(
                    ok=True,
                    compile_stdout=compile_stdout,
                    compile_stderr=compile_stderr,
                    upload_stdout="",
                    upload_stderr="",
                    message="upload disabled by configuration",
                )
            upload_cmd = [
                settings.arduino_cli_path,
                "upload",
                "-p",
                settings.student_port,
                "--fqbn",
                board_fqbn,
                str(sketch_dir),
            ]
            upload_stdout, upload_stderr, upload_ok = await self._run_cmd(upload_cmd)
            return FlashResult(
                ok=upload_ok,
                compile_stdout=compile_stdout,
                compile_stderr=compile_stderr,
                upload_stdout=upload_stdout,
                upload_stderr=upload_stderr,
                message="uploaded" if upload_ok else "upload failed",
            )

    async def flash_baseline(self) -> FlashResult:
        baseline_file = self._find_baseline_file()
        if baseline_file is None:
            return FlashResult(
                ok=False,
                compile_stdout="",
                compile_stderr="",
                upload_stdout="",
                upload_stderr="",
                message="baseline firmware not provided",
            )
        return await self.flash_sketch(
            baseline_file,
            board_fqbn=settings.baseline_fqbn,
            sketch_main=settings.baseline_sketch_main,
        )

    def _prepare_workspace(self, file_path: Path) -> Path:
        ts = int(time.time() * 1000)
        base = Path(settings.data_dir) / "uploads" / "student" / str(ts)
        base.mkdir(parents=True, exist_ok=True)
        if file_path.suffix.lower() == ".zip":
            with zipfile.ZipFile(file_path, "r") as zf:
                zf.extractall(base)
        else:
            sketch_dir = base / file_path.stem
            sketch_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(file_path, sketch_dir / f"{file_path.stem}.ino")
        return base

    def _find_baseline_file(self) -> Path | None:
        base = Path("app") / "baseline_firmware"
        if not base.exists():
            return None
        candidates = list(base.glob("*.ino")) + list(base.glob("*.zip"))
        if not candidates:
            return None
        for preferred in candidates:
            if preferred.name.lower().startswith("baseline"):
                return preferred
        return candidates[0]

    def _resolve_sketch_dir(self, workspace: Path, sketch_main: Optional[str]) -> Path:
        if sketch_main:
            sketch = workspace / sketch_main
            if sketch.exists():
                return sketch.parent
        ino_files = list(workspace.rglob("*.ino"))
        if len(ino_files) == 1:
            return ino_files[0].parent
        raise FileNotFoundError("unable to resolve sketch entry point")

    async def _run_cmd(self, cmd: list[str]) -> tuple[str, str, bool]:
        def _run() -> tuple[str, str, bool]:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            return proc.stdout, proc.stderr, proc.returncode == 0

        return await asyncio.to_thread(_run)
