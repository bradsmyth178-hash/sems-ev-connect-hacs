"""The charger reading shared by the client and the entities.

Lifted verbatim from the Sunlands bridge, which has been exercised against the
GoodWe SEMS API and a hardware simulator, so the field meanings here are the
ones already proven rather than a fresh interpretation.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Snapshot:
    ok: bool = False
    status: int = 0
    status_name: str = "unknown"
    car: int = 0
    power_kw: float = 0.0
    session_kwh: float = 0.0
    lifetime_kwh: float = 0.0
    volt_a: float = 0.0
    curr_a: float = 0.0
    max_power_kw: float = 0.0
    mode: int = 0
    mode_name: str = ""
    comms: int = 0
    faults: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def charging(self) -> bool:
        return self.status == 3

    @property
    def lifetime_wh(self) -> int:
        return int(round(self.lifetime_kwh * 1000))

    @property
    def power_w(self) -> int:
        return int(round(self.power_kw * 1000))
