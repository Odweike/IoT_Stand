import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

import serial


@dataclass
class SerialConfig:
    port: str
    baudrate: int
    name: str


class SerialManager:
    def __init__(
        self,
        config: SerialConfig,
        on_message: Callable[[Dict[str, Any], str], Awaitable[None]],
        sim_mode: bool,
    ) -> None:
        self._config = config
        self._on_message = on_message
        self._sim_mode = sim_mode
        self._serial: Optional[serial.Serial] = None
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._sim_mode:
            return
        try:
            self._serial = serial.Serial(self._config.port, self._config.baudrate, timeout=1)
        except serial.SerialException:
            self._serial = None
            return
        self._task = asyncio.create_task(self._read_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        if self._serial:
            await asyncio.to_thread(self._serial.close)

    async def _read_loop(self) -> None:
        buffer = ""
        while True:
            if not self._serial:
                await asyncio.sleep(1)
                continue
            try:
                data = await asyncio.to_thread(self._serial.read, 256)
            except serial.SerialException:
                await asyncio.sleep(1)
                continue
            if not data:
                await asyncio.sleep(0.05)
                continue
            buffer += data.decode(errors="ignore")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                await self._on_message(payload, self._config.name)

    async def send_command(self, payload: Dict[str, Any]) -> None:
        if self._sim_mode or not self._serial:
            return
        message = json.dumps(payload) + "\n"
        async with self._lock:
            await asyncio.to_thread(self._serial.write, message.encode())

    @staticmethod
    def build_cmd(seq: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "cmd",
            "ver": "0.1",
            "ts": int(time.time() * 1000),
            "seq": seq,
            "set": payload,
        }
