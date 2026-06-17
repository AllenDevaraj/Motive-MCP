from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


Vec3 = Tuple[float, float, float]
QuatWxyz = Tuple[float, float, float, float]


@dataclass(frozen=True)
class PoseSample:
    timestamp_s: float
    position_m: Vec3
    quaternion_wxyz: QuatWxyz


@dataclass(frozen=True)
class BridgeOutput:
    timestamp_s: float
    publish_position_m: Vec3
    publish_velocity_mps: Vec3
