from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional, Protocol

from ..config import StreamConfig
from ..types import PoseSample


class IngestionAdapter(Protocol):
    def connect(self) -> None:
        ...

    def read_sample(self) -> PoseSample:
        ...


@dataclass
class SimulatedIngestionAdapter:
    rate_hz: float

    def __post_init__(self) -> None:
        self._last_emit_s = 0.0
        self._start_s = time.monotonic()

    def connect(self) -> None:
        self._last_emit_s = time.monotonic()

    def read_sample(self) -> PoseSample:
        now = time.monotonic()
        dt_target = 1.0 / self.rate_hz
        dt_wait = dt_target - (now - self._last_emit_s)
        if dt_wait > 0:
            time.sleep(dt_wait)
        t = time.monotonic() - self._start_s
        self._last_emit_s = time.monotonic()

        # Small, smooth motion for deterministic dry-run behavior.
        x = 0.1 * math.cos(0.5 * t)
        y = 0.1 * math.sin(0.5 * t)
        z = 1.03 + 0.01 * math.sin(0.2 * t)
        q_wxyz = (1.0, 0.0, 0.0, 0.0)
        return PoseSample(timestamp_s=time.monotonic(), position_m=(x, y, z), quaternion_wxyz=q_wxyz)


class VrpnIngestionAdapter:
    def __init__(self, stream: StreamConfig) -> None:
        self._stream = stream
        self._tracker = None
        self._latest: Optional[PoseSample] = None

    def connect(self) -> None:
        try:
            import vrpn  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "VRPN package not installed. Install VRPN Python bindings or use --dry-run."
            ) from exc

        tracker_target = f"{self._stream.rigid_body_name}@{self._stream.server_host}:{self._stream.server_port}"
        self._tracker = vrpn.receiver.Tracker(tracker_target)

        def _on_pose(userdata: str, data: dict) -> None:
            position = data.get("position")
            quat = data.get("quaternion")
            if position is None or quat is None:
                return
            # VRPN commonly returns quaternion as x,y,z,w; convert to w,x,y,z.
            q_xyzw = tuple(float(v) for v in quat[:4])
            q_wxyz = (q_xyzw[3], q_xyzw[0], q_xyzw[1], q_xyzw[2])
            self._latest = PoseSample(
                timestamp_s=time.monotonic(),
                position_m=(float(position[0]), float(position[1]), float(position[2])),
                quaternion_wxyz=q_wxyz,
            )

        self._tracker.register_change_handler(self._stream.rigid_body_name, _on_pose, "position")

    def read_sample(self) -> PoseSample:
        if self._tracker is None:
            raise RuntimeError("VRPN adapter not connected")
        for _ in range(200):
            self._tracker.mainloop()
            if self._latest is not None:
                sample = self._latest
                self._latest = None
                return sample
            time.sleep(0.001)
        raise TimeoutError("Timed out waiting for VRPN pose sample")
