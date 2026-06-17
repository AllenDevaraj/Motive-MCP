from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .adapters.ingestion import SimulatedIngestionAdapter, VrpnIngestionAdapter
from .adapters.publisher import NullPublisherAdapter, UnitreeDdsPublisherAdapter
from .bridge import OptiTrackBridge
from .config import load_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OptiTrack -> Unitree DDS bridge starter")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/bridge_config.example.yaml"),
        help="Path to YAML config file",
    )
    parser.add_argument("--dry-run", action="store_true", help="Force simulated ingestion and null publisher")
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Optional runtime limit for testing",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log verbosity",
    )
    return parser


def _configure_logging(level: str) -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return logging.getLogger("optitrack_bridge")


def main() -> None:
    args = _build_parser().parse_args()
    logger = _configure_logging(args.log_level)
    config = load_config(args.config)

    dry_run = args.dry_run or config.bridge.dry_run
    if dry_run:
        ingestion = SimulatedIngestionAdapter(rate_hz=config.bridge.publish_hz)
        publisher = NullPublisherAdapter(logger=logger)
    else:
        if config.stream.protocol != "vrpn":
            raise ValueError(f"Unsupported protocol '{config.stream.protocol}'. Only 'vrpn' is wired today.")
        ingestion = VrpnIngestionAdapter(config.stream)
        if config.dds.enabled:
            publisher = UnitreeDdsPublisherAdapter(
                dds=config.dds,
                topic_name=config.bridge.topic_name,
                logger=logger,
            )
        else:
            logger.warning("dds.enabled=false, using NullPublisherAdapter")
            publisher = NullPublisherAdapter(logger=logger)

    bridge = OptiTrackBridge(config=config, ingestion=ingestion, publisher=publisher, logger=logger)
    bridge.run(max_seconds=args.max_seconds)


if __name__ == "__main__":
    main()
