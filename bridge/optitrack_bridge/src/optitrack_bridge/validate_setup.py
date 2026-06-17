from __future__ import annotations

import argparse
import logging
import socket
import sys
from pathlib import Path
from typing import Callable, List, Tuple

from .adapters.ingestion import SimulatedIngestionAdapter
from .adapters.publisher import NullPublisherAdapter
from .bridge import OptiTrackBridge
from .config import (
    AppConfig,
    DEFAULT_DDS_TOPIC,
    DEFAULT_IMU_OFFSET_M,
    load_config,
)


CheckResult = Tuple[str, bool, str]


def _format_result(result: CheckResult) -> str:
    name, ok, detail = result
    state = "PASS" if ok else "FAIL"
    return f"[{state}] {name}: {detail}"


def _check_python() -> CheckResult:
    ok = sys.version_info >= (3, 10)
    detail = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return ("Python version", ok, detail)


def _check_config(config: AppConfig) -> CheckResult:
    expected_hosts = {"tcp://192.168.50.10", "tcp://192.168.50.24"}
    host_choice = "known-large/small" if config.stream.server_host in expected_hosts else "custom"
    ok = (
        config.bridge.publish_hz > 0
        and config.stream.rigid_body_name.strip() != ""
        and config.stream.protocol == "vrpn"
        and config.bridge.topic_name == DEFAULT_DDS_TOPIC
        and config.stream.server_port == 3883
        and config.dds.domain_id == 0
    )
    detail = (
        f"protocol={config.stream.protocol} rigid_body={config.stream.rigid_body_name} "
        f"host={config.stream.server_host} ({host_choice}) topic={config.bridge.topic_name} "
        f"port={config.stream.server_port} domain={config.dds.domain_id}"
    )
    return ("Config sanity", ok, detail)


def _check_tcp_connectivity(config: AppConfig) -> CheckResult:
    if not config.validation.check_mocap_tcp:
        return ("MoCap TCP reachability", True, "check disabled in config")
    if config.bridge.dry_run:
        return ("MoCap TCP reachability", True, "skipped because dry_run=true")

    host = config.stream.server_host.replace("tcp://", "")
    endpoint = (host, config.stream.server_port)
    timeout_s = config.validation.check_timeout_sec
    try:
        with socket.create_connection(endpoint, timeout=timeout_s):
            return ("MoCap TCP reachability", True, f"connected to {host}:{config.stream.server_port}")
    except OSError as exc:
        return ("MoCap TCP reachability", False, f"cannot connect to {host}:{config.stream.server_port} ({exc})")


def _check_dds_interface(config: AppConfig) -> CheckResult:
    if not config.dds.enabled:
        return ("DDS interface declared", True, "dds.enabled=false")
    if not config.dds.network_interface:
        return ("DDS interface declared", False, "network_interface is empty")
    interfaces = {name for _, name in socket.if_nameindex()}
    interface_present = config.dds.network_interface in interfaces
    is_enx = config.dds.network_interface.lower().startswith("enx")
    ok = interface_present and is_enx
    detail = f"iface={config.dds.network_interface} present={interface_present} enx_pref={is_enx}"
    return ("DDS interface declared", ok, detail)


def _check_tailscale_advisory(config: AppConfig) -> CheckResult:
    if not config.dds.enabled:
        return ("Tailscale advisory", True, "dds.enabled=false")
    interface_names = [name.lower() for _, name in socket.if_nameindex()]
    tailscale_like = [name for name in interface_names if "tailscale" in name]
    if tailscale_like:
        return (
            "Tailscale advisory",
            True,
            "tailscale-like interface detected; ensure tailscale is down before live DDS run",
        )
    return ("Tailscale advisory", True, "no tailscale-like interface name detected")


def _check_transform_strategy(config: AppConfig) -> CheckResult:
    expected_offset = tuple(DEFAULT_IMU_OFFSET_M)
    offset_match = tuple(round(v, 5) for v in config.transform.imu_offset_m) == expected_offset
    if config.transform.rigid_body_origin_is_imu_site:
        detail = (
            "recommended mode enabled: tracking IMU site directly (no bridge offset math in default path)"
        )
        return ("Transform strategy", True, detail)
    if not offset_match:
        return (
            "Transform strategy",
            False,
            f"pelvis-origin mode selected but imu_offset_m != {expected_offset}",
        )
    return (
        "Transform strategy",
        True,
        f"alternate pelvis-origin mode enabled with IMU_OFFSET={expected_offset}",
    )


def _check_motion_test_guidance(_config: AppConfig) -> CheckResult:
    detail = (
        "required live motion test: +1m forward->x+, +1m left->lateral sign check, +0.5m lift->z+; "
        "do not assume axis mapping without empirical verification"
    )
    return ("Frame motion-test guidance", True, detail)


def _check_network_guidance(_config: AppConfig) -> CheckResult:
    detail = (
        "live runs require bridge host on both 192.168.50.x (MoCap) and 192.168.123.x (robot DDS) "
        "at the same time"
    )
    return ("Dual-network guidance", True, detail)


def _check_optional_imports(config: AppConfig) -> CheckResult:
    missing = []
    if not config.bridge.dry_run and config.stream.protocol == "vrpn":
        try:
            import vrpn  # type: ignore
        except ImportError:
            missing.append("vrpn")
    if not config.bridge.dry_run and config.dds.enabled:
        try:
            import unitree_sdk2py  # type: ignore
        except ImportError:
            missing.append("unitree_sdk2py")
    ok = len(missing) == 0
    detail = "all required optional deps found" if ok else f"missing: {', '.join(missing)}"
    return ("Optional dependency availability", ok, detail)


def _check_dry_run_loop(config: AppConfig) -> CheckResult:
    logger = logging.getLogger("optitrack_bridge_validate")
    bridge = OptiTrackBridge(
        config=config,
        ingestion=SimulatedIngestionAdapter(rate_hz=max(50.0, config.bridge.publish_hz)),
        publisher=NullPublisherAdapter(logger=logger),
        logger=logger,
    )
    bridge.run(max_seconds=0.25)
    ok = bridge.stats.published_count > 0
    return (
        "Dry-run publish loop",
        ok,
        f"published={bridge.stats.published_count} dropped={bridge.stats.dropped_count}",
    )


def run_checks(config_path: Path) -> int:
    config = load_config(config_path)
    checks: List[Callable[[], CheckResult]] = [
        _check_python,
        lambda: _check_config(config),
        lambda: _check_tcp_connectivity(config),
        lambda: _check_dds_interface(config),
        lambda: _check_tailscale_advisory(config),
        lambda: _check_optional_imports(config),
        lambda: _check_transform_strategy(config),
        lambda: _check_dry_run_loop(config),
        lambda: _check_network_guidance(config),
        lambda: _check_motion_test_guidance(config),
    ]
    results = [check() for check in checks]
    for result in results:
        print(_format_result(result))
    fail_count = sum(1 for _, ok, _ in results if not ok)
    print(f"\nSummary: {len(results) - fail_count}/{len(results)} checks passed")
    return 1 if fail_count else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate OptiTrack bridge setup")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/bridge_config.example.yaml"),
        help="Path to YAML config file",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    raise SystemExit(run_checks(args.config))


if __name__ == "__main__":
    main()
