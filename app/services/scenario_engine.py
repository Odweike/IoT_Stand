import asyncio
import random
import time
from dataclasses import dataclass
from typing import Optional

from app.services.serial_manager import SerialManager
from app.services.telemetry_service import TelemetrySimulator


@dataclass
class RandomScenarioConfig:
    min_power: int
    max_power: int
    on_min_s: int
    on_max_s: int
    off_min_s: int
    off_max_s: int


class ScenarioEngine:
    def __init__(self, serial_manager: SerialManager, simulator: TelemetrySimulator | None) -> None:
        self._serial = serial_manager
        self._simulator = simulator
        self._task: Optional[asyncio.Task] = None
        self._seq = 1

    async def set_manual(self, power: int) -> None:
        await self.stop()
        await self._send_heater(power)

    async def start_random(self, config: RandomScenarioConfig) -> None:
        await self.stop()
        self._task = asyncio.create_task(self._random_loop(config))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
        await self._send_heater(0)

    async def _random_loop(self, config: RandomScenarioConfig) -> None:
        while True:
            power = random.randint(config.min_power, config.max_power)
            await self._send_heater(power)
            await asyncio.sleep(random.uniform(config.on_min_s, config.on_max_s))
            await self._send_heater(0)
            await asyncio.sleep(random.uniform(config.off_min_s, config.off_max_s))

    async def _send_heater(self, power: int) -> None:
        if self._simulator:
            self._simulator.set_heater(power)
        cmd = SerialManager.build_cmd(self._seq, {"heater": power})
        self._seq += 1
        await self._serial.send_command(cmd)
