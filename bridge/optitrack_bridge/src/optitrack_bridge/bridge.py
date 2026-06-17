from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from .config import AppConfig
from .types import BridgeOutput, PoseSample, Vec3
from .adapters.ingestion import IngestionAdapter
from .adapters.publisher import PublisherAdapter


def _quat_conjugate(q: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    w, x, y, z = q
    return (w, -x, -y, -z)


def _quat_mul(
    a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]
) -> Tuple[float, float, float, float]:
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def _rotate_vec(q_wxyz: Tuple[float, float, float, float], v: Vec3) -> Vec3:
    q_norm = math.sqrt(sum(x * x for x in q_wxyz))
    if q_norm <= 1e-9:
        return v
    q = tuple(x / q_norm for x in q_wxyz)
    p = (0.0, v[0], v[1], v[2])
    rotated = _quat_mul(_quat_mul(q, p), _quat_conjugate(q))
    return (rotated[1], rotated[2], rotated[3])


@dataclass
class BridgeStats:
    published_count: int = 0
    dropped_count: int = 0


class OptiTrackBridge:
    def __init__(
        self,
        config: AppConfig,
        ingestion: IngestionAdapter,
        publisher: PublisherAdapter,
        logger: logging.Logger,
    ) -> None:
        self._config = config
        self._ingestion = ingestion
        self._publisher = publisher
        self._logger = logger
        self._stats = BridgeStats()
        self._last_output: Optional[BridgeOutput] = None

    @property
    def stats(self) -> BridgeStats:
        return self._stats

    def _to_publish_position(self, sample: PoseSample) -> Vec3:
        if self._config.transform.rigid_body_origin_is_imu_site:
            # Recommended path: track IMU site directly in Motive and publish as-is.
            return sample.position_m
        # Alternate path: if tracking pelvis-frame origin, rotate pelvis->IMU offset by IMU orientation.
        rotated = _rotate_vec(sample.quaternion_wxyz, self._config.transform.imu_offset_m)
        return (
            sample.position_m[0] + rotated[0],
            sample.position_m[1] + rotated[1],
            sample.position_m[2] + rotated[2],
        )

    def _estimate_velocity(self, now_s: float, pos_m: Vec3) -> Vec3:
        if not self._config.bridge.velocity_from_position or self._last_output is None:
            return (0.0, 0.0, 0.0)
        dt = now_s - self._last_output.timestamp_s
        if dt <= 1e-6:
            return self._last_output.publish_velocity_mps
        return (
            (pos_m[0] - self._last_output.publish_position_m[0]) / dt,
            (pos_m[1] - self._last_output.publish_position_m[1]) / dt,
            (pos_m[2] - self._last_output.publish_position_m[2]) / dt,
        )

    def run(self, max_seconds: Optional[float] = None) -> None:
        self._ingestion.connect()
        self._publisher.connect()
        self._logger.info(
            "Bridge started protocol=%s dry_run=%s publish_hz=%.1f topic=%s",
            self._config.stream.protocol,
            self._config.bridge.dry_run,
            self._config.bridge.publish_hz,
            self._config.bridge.topic_name,
        )
        if self._config.stream.protocol == "vrpn":
            self._logger.info(
                "VRPN target tracker=%s endpoint=%s:%d (recommended Motive 2.2 path)",
                self._config.stream.rigid_body_name,
                self._config.stream.server_host,
                self._config.stream.server_port,
            )
        if self._config.transform.rigid_body_origin_is_imu_site:
            self._logger.info(
                "Using IMU-site tracking mode: publish position directly; orientation comes from rt/lowstate."
            )
        else:
            self._logger.info(
                "Using pelvis-origin mode: applying rotated IMU offset %s to publish IMU-site position.",
                self._config.transform.imu_offset_m,
            )
        if self._config.bridge.velocity_from_position:
            self._logger.info(
                "velocity_from_position=true (optional helper; controller may re-derive velocity from position)."
            )
        else:
            self._logger.info(
                "velocity_from_position=false (publishing zero velocity unless ingestion provides one)."
            )
        deadline = None if max_seconds is None else (time.monotonic() + max_seconds)
        next_log_s = time.monotonic() + self._config.bridge.log_interval_sec

        while True:
            if deadline is not None and time.monotonic() >= deadline:
                self._logger.info("Bridge run reached max_seconds=%.2f", max_seconds)
                return
            try:
                sample = self._ingestion.read_sample()
                publish_position_m = self._to_publish_position(sample)
                publish_velocity_mps = self._estimate_velocity(sample.timestamp_s, publish_position_m)
                output = BridgeOutput(
                    timestamp_s=sample.timestamp_s,
                    publish_position_m=publish_position_m,
                    publish_velocity_mps=publish_velocity_mps,
                )
                self._publisher.publish(output)
                self._last_output = output
                self._stats.published_count += 1
            except Exception as exc:
                self._stats.dropped_count += 1
                self._logger.warning("Bridge cycle error: %s", exc)

            now_s = time.monotonic()
            if now_s >= next_log_s:
                self._logger.info(
                    "health published=%d dropped=%d",
                    self._stats.published_count,
                    self._stats.dropped_count,
                )
                next_log_s = now_s + self._config.bridge.log_interval_sec
