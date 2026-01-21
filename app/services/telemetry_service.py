import asyncio
import math
import random
import time
from typing import Any, Dict, Set

from fastapi import WebSocket

from app.services.db import Database, TelemetryRecord


class TelemetryService:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._latest: Dict[str, Any] | None = None
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    def latest(self) -> Dict[str, Any] | None:
        return self._latest

    async def register(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
        if self._latest:
            await websocket.send_json(self._latest)

    async def unregister(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def update(self, payload: Dict[str, Any], source_device: str) -> None:
        self._latest = payload
        fan_values = payload.get("fan") or []
        fan1 = fan_values[0] if len(fan_values) > 0 else None
        fan2 = fan_values[1] if len(fan_values) > 1 else None
        fan3 = fan_values[2] if len(fan_values) > 2 else None
        await self._db.insert_telemetry(
            TelemetryRecord(
                ts=int(payload.get("ts", time.time() * 1000)),
                t1=payload.get("t1"),
                t2=payload.get("t2"),
                p1=payload.get("p1"),
                p2=payload.get("p2"),
                flow=payload.get("flow"),
                heater=payload.get("heater"),
                pump=payload.get("pump"),
                fan1=fan1,
                fan2=fan2,
                fan3=fan3,
                fault=payload.get("fault"),
                source_device=source_device,
            )
        )
        await self._broadcast(payload)

    async def _broadcast(self, payload: Dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self._clients)
        if not clients:
            return
        for ws in clients:
            try:
                await ws.send_json(payload)
            except Exception:
                await self.unregister(ws)


class TelemetrySimulator:
    def __init__(self, telemetry: TelemetryService) -> None:
        self._telemetry = telemetry
        self._task: asyncio.Task | None = None
        self._heater = 0
        self._pump = 0
        self._fan = [0, 0, 0]
        self._t1 = 23.0
        self._t2 = 25.0
        self._p1 = 1.0
        self._p2 = 1.0
        self._flow = 2.0
        self._phase = 0.0

    def set_heater(self, power: int) -> None:
        self._heater = max(0, min(100, int(power)))

    def set_actuators(self, pump: int, fan: list[int]) -> None:
        self._pump = max(0, min(255, int(pump)))
        self._fan = [max(0, min(255, int(v))) for v in fan]

    async def start(self) -> None:
        if self._task:
            return
        self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while True:
            self._phase += 0.2
            heater_effect = (self._heater / 100.0) * 0.3
            pump_cool = (self._pump / 255.0) * 0.2
            fan_cool = (sum(self._fan) / 765.0) * 0.2
            ambient = 23.0 + math.sin(self._phase / 10) * 0.4
            self._t1 += heater_effect - (pump_cool + fan_cool) * 0.8
            self._t2 += heater_effect * 0.6 - (pump_cool + fan_cool)
            self._t1 = max(18.0, min(80.0, self._t1))
            self._t2 = max(18.0, min(85.0, self._t2))
            self._t1 += (ambient - self._t1) * 0.02
            self._t2 += (ambient - self._t2) * 0.01

            self._p1 = 1.0 + random.uniform(-0.05, 0.05)
            self._p2 = 1.0 + random.uniform(-0.05, 0.05)
            self._flow = 2.0 + (self._pump / 255.0) * 3.0 + random.uniform(-0.2, 0.2)

            payload = {
                "type": "telemetry",
                "ver": "0.1",
                "ts": int(time.time() * 1000),
                "t1": round(self._t1, 2),
                "t2": round(self._t2, 2),
                "p1": round(self._p1, 2),
                "p2": round(self._p2, 2),
                "flow": round(self._flow, 2),
                "heater": self._heater,
                "pump": self._pump,
                "fan": self._fan,
                "fault": 0,
            }
            await self._telemetry.update(payload, "simulator")
            await asyncio.sleep(0.2)
