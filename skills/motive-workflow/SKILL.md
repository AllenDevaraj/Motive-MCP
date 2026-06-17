---
name: motive-workflow
description: Use when driving the lab's OptiTrack Motive system through the `motive` MCP server — to initialize the engine, load calibration, manage the H1-2 pelvis rigid body, enable VRPN/NatNet streaming, or check tracking status. Covers the correct tool order and the Unitree H1-2 frame/rigid-body conventions. Triggers on "set up the mocap stream", "enable VRPN", "is the pelvis tracked", "stream the H1-2 pose to MJPC".
---

# Driving Motive via the MCP server

The `motive` MCP server runs on the Windows OptiTrack PC and wraps the Motive 2.2 NPTrackingTools
API. It does **load-calibration + rigid-body management + streaming control** — Motive 2.2 does
**not** expose wand calibration through the API, so wanding stays a human GUI step (and the rig is
already calibrated). Your job is the software side around that.

## Hard constraints (state these to the operator before initializing)

- **The Motive GUI must be CLOSED** before `initialize()` — the API takes ownership of the cameras.
  After `shutdown()` the operator can reopen the GUI.
- This is a **shared lab machine** (CU Boulder ARPG). When loading rigid bodies, use `load_rigid_bodies(..., replace=false)` (add, don't replace) so you never clobber other projects' assets. Do not remove bodies you didn't create.

## Standard sequence

1. `initialize(calibration_path=..., profile_path=...)` — start the engine. Load a recent good
   calibration if not already in the profile. A known-good one on the PC:
   `C:\Users\arpg\Desktop\Calibration Exceptional (MeanErr 0.379 mm) 2026-02-17 4.cal`.
2. `status()` — confirm cameras detected and list rigid bodies.
3. Ensure the H1-2 base body exists:
   - if a `.tra`/`.motive` for it exists → `load_rigid_bodies(path, replace=false)`;
   - else `create_rigid_body("h1_2_pelvis", marker_xyz_m, rb_id=1)` from pelvis markers.
   - `set_rigid_body_enabled("h1_2_pelvis", true)`.
4. `set_frame_rate(240)` (or whatever the volume supports; ≥ planner rate ~60 Hz).
5. `rigid_body_pose("h1_2_pelvis")` — sanity check: `tracked=true`, `mean_error_mm` small (~<2 mm),
   and `z` ≈ the real height of the tracked point above the floor.
6. `enable_vrpn(3883)` — start streaming. The Linux bridge then consumes
   `h1_2_pelvis@tcp://<motive-pc-ip>:3883` → `rt/sportmodestate`.
7. When done: `shutdown()` (releases cameras so the GUI can reopen).

## H1-2 conventions (must match the controller — see OPTITRACK_HANDOFF.md)

- **Rigid-body name:** `h1_2_pelvis`.
- **Tracked point = the pelvis IMU site.** Set the rigid-body pivot at the physical IMU so the
  streamed position is the IMU-site pose the node expects; the node backs out the pelvis with
  `IMU_OFFSET = [-0.04452, -0.01891, 0.27756] m`. Orientation comes from the robot IMU, not mocap.
- **World frame:** z-up, floor at z=0, +x = robot forward. (Set the ground plane in the GUI to match;
  the API can't set it in 2.2.)
- **Streaming:** VRPN (TCP 3883). The node only needs accurate **position**; it re-derives velocity.

## Verifying the stream lands (Linux side)

Run in the `h1_mujoco` venv: `python dds_tools/dds_topic_check.py --extra rt/sportmodestate`
→ expect it ARRIVING and finite after the bridge is up. Move the rigid body and confirm the pose
changes on the expected axes (locks the frame convention).

## Gotchas

- If `initialize()` fails as "in use", the Motive GUI (or another API app) still holds the cameras.
- `status()` showing 0 cameras → check the camera/PoE link, not the API.
- DHCP can change the PC's IP; confirm the current one (`run_server.ps1` prints it) and update the
  `claude mcp add` URL / `.mcp.json` accordingly.
