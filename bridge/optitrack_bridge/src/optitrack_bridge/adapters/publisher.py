from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from ..config import DdsConfig
from ..types import BridgeOutput


class PublisherAdapter(Protocol):
    def connect(self) -> None:
        ...

    def publish(self, output: BridgeOutput) -> None:
        ...


@dataclass
class NullPublisherAdapter:
    logger: logging.Logger

    def connect(self) -> None:
        self.logger.info("Using NullPublisherAdapter (dry-run mode).")

    def publish(self, output: BridgeOutput) -> None:
        _ = output


class UnitreeDdsPublisherAdapter:
    def __init__(self, dds: DdsConfig, topic_name: str, logger: logging.Logger) -> None:
        self._dds = dds
        self._topic_name = topic_name
        self._logger = logger
        self._publisher = None

    def connect(self) -> None:
        try:
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize  # type: ignore
            from unitree_sdk2py.core.channel import ChannelPublisher  # type: ignore
            from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "unitree_sdk2py is not installed. Install it or set dds.enabled=false / --dry-run."
            ) from exc

        ChannelFactoryInitialize(self._dds.domain_id, self._dds.network_interface)
        self._publisher = ChannelPublisher(self._topic_name, SportModeState_)
        self._publisher.Init()
        self._logger.info(
            "Unitree DDS publisher initialized: topic=%s domain=%d iface=%s",
            self._topic_name,
            self._dds.domain_id,
            self._dds.network_interface,
        )

    def publish(self, output: BridgeOutput) -> None:
        if self._publisher is None:
            raise RuntimeError("DDS publisher not connected")

        # Keep mapping explicit: only position[0:3] and velocity[0:3] are written.
        # Orientation is intentionally not published by this bridge (comes from rt/lowstate IMU).
        msg = self._publisher.msg_type()
        msg.position[0] = output.publish_position_m[0]
        msg.position[1] = output.publish_position_m[1]
        msg.position[2] = output.publish_position_m[2]
        msg.velocity[0] = output.publish_velocity_mps[0]
        msg.velocity[1] = output.publish_velocity_mps[1]
        msg.velocity[2] = output.publish_velocity_mps[2]
        self._publisher.Write(msg)
