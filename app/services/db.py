import json
import os
import sqlite3
import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class TelemetryRecord:
    ts: int
    t1: float | None
    t2: float | None
    p1: float | None
    p2: float | None
    flow: float | None
    heater: int | None
    pump: int | None
    fan1: int | None
    fan2: int | None
    fan3: int | None
    fault: int | None
    source_device: str


class Database:
    def __init__(self, db_path: str) -> None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = asyncio.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
                ts INTEGER,
                t1 REAL,
                t2 REAL,
                p1 REAL,
                p2 REAL,
                flow REAL,
                heater INTEGER,
                pump INTEGER,
                fan1 INTEGER,
                fan2 INTEGER,
                fan3 INTEGER,
                fault INTEGER,
                source_device TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                ts INTEGER,
                role TEXT,
                action TEXT,
                payload_json TEXT
            )
            """
        )
        self._conn.commit()

    async def insert_telemetry(self, record: TelemetryRecord) -> None:
        async with self._lock:
            await asyncio.to_thread(self._insert_telemetry_sync, record)

    def _insert_telemetry_sync(self, record: TelemetryRecord) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO telemetry (
                ts, t1, t2, p1, p2, flow, heater, pump, fan1, fan2, fan3, fault, source_device
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.ts,
                record.t1,
                record.t2,
                record.p1,
                record.p2,
                record.flow,
                record.heater,
                record.pump,
                record.fan1,
                record.fan2,
                record.fan3,
                record.fault,
                record.source_device,
            ),
        )
        self._conn.commit()

    async def insert_event(self, role: str, action: str, payload: Dict[str, Any]) -> None:
        async with self._lock:
            await asyncio.to_thread(self._insert_event_sync, role, action, payload)

    def _insert_event_sync(self, role: str, action: str, payload: Dict[str, Any]) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO events (ts, role, action, payload_json) VALUES (?, ?, ?, ?)",
            (int(time.time() * 1000), role, action, json.dumps(payload)),
        )
        self._conn.commit()


_db_instance: Database | None = None


def get_db(db_path: str) -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
    return _db_instance
