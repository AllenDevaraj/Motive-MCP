# OptiTrack Bridge Quick Checklist

This checklist mirrors the current success criteria and defaults from `answers_from_main.md`.

## Required defaults

- Rigid body default name: `h1_2_pelvis`
- Protocol default: VRPN (recommended for Motive 2.2)
- VRPN endpoint default: `tcp://192.168.50.10:3883`
- Alternate Motive host option: `tcp://192.168.50.24:3883`
- DDS topic: `rt/sportmodestate`
- DDS domain ID (real robot): `0`
- Published fields: `position[0:3]`, `velocity[0:3]` only
- Orientation source: not this bridge (comes from IMU / `rt/lowstate`)
- IMU_OFFSET constant in pelvis frame: `[-0.04452, -0.01891, 0.27756]`

## Recommended tracking strategy

- Preferred: track IMU site directly in Motive and publish position directly (no offset math in bridge).
- Alternate option 2: if tracking pelvis origin, publish IMU-site position using rotated IMU_OFFSET.

## Frame convention and motion test

- Target frame convention: world z-up, floor z=0, +x forward.
- Do not trust assumed axis mapping without empirical checks.
- Required motion checks:
  - Move tracked point +1 m forward -> `position.x` increases by ~1.0
  - Move +1 m left -> lateral axis moves with correct sign
  - Lift +0.5 m -> `position.z` increases by ~0.5

## Network pitfalls

- Bridge host must reach both networks:
  - `192.168.50.x` (MoCap)
  - `192.168.123.x` (robot DDS)
- Pin DDS NIC to wired `enx*` interface.
- Keep Tailscale down for live DDS discovery/publish.
- Ensure Motive firewall allows VRPN TCP port `3883`.

## Success criteria checklist

1. Topic is alive: `rt/sportmodestate` arriving at expected rate (target 200 Hz, planner minimum roughly 50-65 Hz), finite values, decoded position present.
2. Static test: with rigid body held still, velocity is near zero and position is stable.
3. Motion test: forward/left/lift checks pass with expected signs and magnitudes.
4. Height sanity: published IMU-site z matches measured tracked-point height.
5. Planner margin sanity: errors should stay well below approximately 10 cm position / 0.3 m/s velocity sensitivity.
6. Optional comparison: compare against software estimator recording for smoothness and drift behavior.
