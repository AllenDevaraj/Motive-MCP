# OptiTrack -> Unitree DDS Bridge (Standalone Bring-up Package)

This package is a PC-local starter for bringing up an OptiTrack-to-Unitree DDS bridge without modifying upstream repos.

It is intentionally practical and conservative:
- VRPN-first ingestion path for Motive 2.2 (with a simulated mode for offline testing).
- Clear adapter split between OptiTrack ingestion and DDS publication.
- Runtime health logging.
- Validation helpers to confirm setup facts before live bring-up.

This package does **not** claim live hardware validation is complete.

## Source of Truth

- `answers_from_main.md` (authoritative current defaults and constraints)
- `OPTITRACK_HANDOFF.md` (integration contract and network constraints)
- `Getting started with OptiTrack.pdf` (Motive operation steps)

This bridge scaffold is aligned to `answers_from_main.md`.

## Architecture

`optitrack_bridge/src/optitrack_bridge` contains:

- `main.py`: CLI entrypoint.
- `bridge.py`: bridge loop, health reporting, position/velocity handling.
- `config.py`: config schema + loader.
- `types.py`: shared sample/status dataclasses.
- `adapters/ingestion.py`: ingestion interfaces and implementations.
  - `SimulatedIngestionAdapter` (dry-run mode)
  - `VrpnIngestionAdapter` (stubbed integration path if `vrpn` is available)
- `adapters/publisher.py`: publisher interfaces and implementations.
  - `NullPublisherAdapter` (dry-run)
  - `UnitreeDdsPublisherAdapter` (integration stub for `unitree_sdk2py`)
- `validate_setup.py`: pass/fail setup checks.

## Prerequisites

- Windows host with PowerShell.
- Python 3.10+ recommended.
- Access to both networks for live use:
  - OptiTrack network (`192.168.50.x`, typically WiFi)
  - Unitree DDS network (`192.168.123.x`, typically wired dongle/NIC)

Optional for live integration:
- `vrpn` Python bindings (for VRPN ingestion)
- `unitree_sdk2py` (for DDS publish path)

## Quick Start (Dry-Run First)

From `optitrack_bridge`:

1. Create venv and install deps:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1`
2. Validate setup (offline checks + dry-run bridge spin):
   - `powershell -ExecutionPolicy Bypass -File .\scripts\validate_setup.ps1`
3. Run bridge in dry-run mode:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\run_dryrun.ps1`

You should see periodic health logs with publish counts.

## Live Bring-up Steps (Hardware Online)

1. In Motive, complete calibration steps from `Getting started with OptiTrack.pdf`.
2. Ensure project frame convention follows handoff contract:
   - world is z-up
   - floor at `z = 0`
   - `x` points robot-forward
3. Define rigid body in Motive:
   - recommended default name: `h1_2_pelvis`
   - recommended strategy: track the IMU site directly (pivot/origin at IMU site)
4. Prefer VRPN:
   - Data Streaming pane: Transmission Type = Unicast, Broadcast VRPN = On
   - note Local Interface IP (`192.168.50.10` larger system or `192.168.50.24` smaller)
   - default VRPN endpoint uses TCP port `3883`
5. Edit `config/bridge_config.example.yaml` for:
   - rigid body name and chosen Motive host (`.10` or `.24`)
   - robot DDS interface name (pin wired `enx*` NIC)
   - whether your rigid-body origin is already the IMU site (recommended true)
   - keep DDS domain id `0` for real robot
6. Validate live prerequisites:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\validate_setup.ps1 -ConfigPath .\config\bridge_config.example.yaml`
7. Run bridge:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\run_bridge.ps1 -ConfigPath .\config\bridge_config.example.yaml`

## Important Defaults and Assumptions

- Recommended rigid-body name default: `h1_2_pelvis`
- DDS topic: `rt/sportmodestate`
- Publish rate target: `200 Hz` default
- Protocol preference: `VRPN` first (Motive 2.2)
- VRPN endpoint default: `tcp://192.168.50.10:3883` (or `.24:3883` for small setup)
- Domain ID default: `0` for real robot
- Coordinate assumptions: world z-up, floor z=0, x-forward
- Message mapping: only `position[0:3]` and `velocity[0:3]`; orientation is not from this bridge
- IMU_OFFSET constant (pelvis frame): `[-0.04452, -0.01891, 0.27756]` m
- Recommended transform strategy: track IMU site directly (no offset math in bridge default path)
- Alternate strategy: if tracking pelvis origin, publish IMU-site position via rotated IMU_OFFSET

## Network Guidance

- Bridge host must straddle both networks simultaneously:
  - MoCap: `192.168.50.x` (typically WiFi)
  - Robot DDS: `192.168.123.x` (typically wired USB-Ethernet `enx*`)
- Pin DDS NIC to wired `enx*` interface for live robot runs.
- Keep Tailscale down during live DDS runs to avoid wrong locator advertisement.
- On Motive host, allow streaming through firewall (`3883` TCP for VRPN).

## Frame Validation Warning

- Do not assume axis mapping from theory alone.
- Validate empirically with motion tests before trusting live control:
  - move +1 m robot-forward -> `position.x` should increase by ~1
  - move +1 m left -> lateral axis sign should match expectation
  - lift +0.5 m -> `position.z` should increase by ~0.5

See `docs/quick_checklist.md` for the full success criteria checklist.

## Success Criteria (Q6)

- `rt/sportmodestate` is alive at expected rate with finite decoded position.
- Static hold shows stable position and near-zero velocity.
- Motion test validates axis/sign mapping (forward/left/lift checks).
- Height sanity matches measured IMU-site height and expected pelvis recovery behavior.
- Position/velocity quality stays comfortably inside planner sensitivity margins.
- Optional parity run against software estimator confirms smooth, drift-resistant behavior.

## What Is Stubbed vs Implemented

Implemented now:
- Config loading
- Simulated input mode
- Bridge loop and health reporting
- Optional finite-difference velocity
- Validation script and PowerShell quickstart scripts

Stubbed integration points (environment dependent):
- VRPN runtime ingestion (requires `vrpn` package and live server)
- Unitree DDS publisher wiring (requires `unitree_sdk2py` and matching IDL/runtime environment)

## Validation Expectations

`validate_setup.py` reports `PASS`/`FAIL` for:
- config readability and basic values
- network reachability placeholders
- optional library availability
- dry-run bridge loop publishing
- motion-test and networking advisories

Even if these pass, you still must verify with hardware online:
- Motive stream quality and rigid-body continuity
- real VRPN ingestion stability
- real DDS publish visibility on robot network
- frame alignment by motion test
- IMU-site strategy correctness (or alternate offset math correctness)

## Notes for Later Repo Integration

- Keep `src/optitrack_bridge` as the importable module root.
- Replace TODO-marked stubs in adapters.
- Add project-specific message mapping once exact Unitree bindings are available on this PC.
