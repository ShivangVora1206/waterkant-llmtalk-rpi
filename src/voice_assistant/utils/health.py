"""System health monitoring — CPU, RAM, temperature, throttle."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _vcgencmd(cmd: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["vcgencmd", cmd],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def get_health_snapshot() -> dict[str, Any]:
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        temp_raw = _vcgencmd("measure_temp")
        throttle_raw = _vcgencmd("get_throttled")

        temp_c: Optional[float] = None
        if temp_raw:
            try:
                temp_c = float(temp_raw.replace("temp=", "").replace("'C", ""))
            except ValueError:
                pass

        throttled = False
        if throttle_raw:
            try:
                val = int(throttle_raw.split("=")[1], 16)
                throttled = bool(val & 0xF)  # current throttling bits
            except (IndexError, ValueError):
                pass

        return {
            "cpu_percent": cpu,
            "ram_total_mb": mem.total // 1024**2,
            "ram_used_mb": mem.used // 1024**2,
            "ram_free_mb": mem.available // 1024**2,
            "temp_c": temp_c,
            "throttled": throttled,
        }
    except ImportError:
        return {"error": "psutil not available"}


class HealthMonitor:
    def __init__(self, event_bus: Any, interval_s: float = 5.0) -> None:
        self._bus = event_bus
        self._interval = interval_s
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="health_monitor")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        while True:
            try:
                snapshot = get_health_snapshot()
                await self._bus.publish("system.health", snapshot)
            except Exception as exc:
                logger.debug("Health monitor error: %s", exc)
            await asyncio.sleep(self._interval)
