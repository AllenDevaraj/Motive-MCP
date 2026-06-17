from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

from .types import Vec3

DEFAULT_RIGID_BODY_NAME = "h1_2_pelvis"
DEFAULT_VRPN_HOST = "tcp://192.168.50.10"
DEFAULT_VRPN_PORT = 3883
DEFAULT_DDS_TOPIC = "rt/sportmodestate"
DEFAULT_IMU_OFFSET_M = [-0.04452, -0.01891, 0.27756]


@dataclass(frozen=True)
class StreamConfig:
    protocol: str
    rigid_body_name: str
    server_host: str
    server_port: int


@dataclass(frozen=True)
class BridgeConfig:
    dry_run: bool
    publish_hz: float
    velocity_from_position: bool
    log_interval_sec: float
    topic_name: str


@dataclass(frozen=True)
class DdsConfig:
    enabled: bool
    domain_id: int
    network_interface: str


@dataclass(frozen=True)
class TransformConfig:
    imu_offset_m: Vec3
    rigid_body_origin_is_imu_site: bool


@dataclass(frozen=True)
class FrameConfig:
    world_z_up: bool
    floor_z0: bool
    x_forward: bool


@dataclass(frozen=True)
class ValidationConfig:
    check_mocap_tcp: bool
    check_timeout_sec: float


@dataclass(frozen=True)
class AppConfig:
    stream: StreamConfig
    bridge: BridgeConfig
    dds: DdsConfig
    transform: TransformConfig
    frame: FrameConfig
    validation: ValidationConfig


def _to_vec3(value: Any) -> Vec3:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("imu_offset_m must be a 3-item list/tuple")
    return (float(value[0]), float(value[1]), float(value[2]))


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = yaml.safe_load(f) or {}

    stream_raw = data.get("stream", {})
    bridge_raw = data.get("bridge", {})
    dds_raw = data.get("dds", {})
    transform_raw = data.get("transform", {})
    frame_raw = data.get("frame", {})
    validation_raw = data.get("validation", {})

    stream = StreamConfig(
        protocol=str(stream_raw.get("protocol", "vrpn")).strip().lower(),
        rigid_body_name=str(stream_raw.get("rigid_body_name", DEFAULT_RIGID_BODY_NAME)),
        server_host=str(stream_raw.get("server_host", DEFAULT_VRPN_HOST)),
        server_port=int(stream_raw.get("server_port", DEFAULT_VRPN_PORT)),
    )
    bridge = BridgeConfig(
        dry_run=bool(bridge_raw.get("dry_run", True)),
        publish_hz=float(bridge_raw.get("publish_hz", 200.0)),
        velocity_from_position=bool(bridge_raw.get("velocity_from_position", True)),
        log_interval_sec=float(bridge_raw.get("log_interval_sec", 1.0)),
        topic_name=str(bridge_raw.get("topic_name", DEFAULT_DDS_TOPIC)),
    )
    dds = DdsConfig(
        enabled=bool(dds_raw.get("enabled", False)),
        domain_id=int(dds_raw.get("domain_id", 0)),
        network_interface=str(dds_raw.get("network_interface", "")),
    )
    transform = TransformConfig(
        imu_offset_m=_to_vec3(transform_raw.get("imu_offset_m", DEFAULT_IMU_OFFSET_M)),
        rigid_body_origin_is_imu_site=bool(transform_raw.get("rigid_body_origin_is_imu_site", True)),
    )
    frame = FrameConfig(
        world_z_up=bool(frame_raw.get("world_z_up", True)),
        floor_z0=bool(frame_raw.get("floor_z0", True)),
        x_forward=bool(frame_raw.get("x_forward", True)),
    )
    validation = ValidationConfig(
        check_mocap_tcp=bool(validation_raw.get("check_mocap_tcp", True)),
        check_timeout_sec=float(validation_raw.get("check_timeout_sec", 1.0)),
    )

    if bridge.publish_hz <= 0.0:
        raise ValueError("publish_hz must be > 0")
    if bridge.log_interval_sec <= 0.0:
        raise ValueError("log_interval_sec must be > 0")
    if stream.server_port <= 0:
        raise ValueError("server_port must be > 0")
    if validation.check_timeout_sec <= 0.0:
        raise ValueError("check_timeout_sec must be > 0")

    return AppConfig(
        stream=stream,
        bridge=bridge,
        dds=dds,
        transform=transform,
        frame=frame,
        validation=validation,
    )
