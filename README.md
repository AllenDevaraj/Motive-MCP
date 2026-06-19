# motive-mocap — OptiTrack → Unitree H1-2 base publisher

Stream the **H1-2 pelvis pose** from the lab's **OptiTrack Motive** system onto the robot's
DDS as `rt/sportmodestate`, so the MJPC controller gets a ground-truth base pose/velocity.

## The simple way: one file

**`publish_sportmodestate.py`** does the whole job in a single script — reads the pelvis
rigid body from Motive, converts it to the robot world frame, and publishes `rt/sportmodestate`.
No server, no extra processes.

```
   Motive (cameras + cal)  ──►  publish_sportmodestate.py  ──►  rt/sportmodestate (DDS)  ──►  MJPC node
        NPTrackingTools DLL          read → convert → publish
```

### Run it
1. **Where:** on a machine that has **Motive installed** *and* a **route to the robot's DDS
   network** (`192.168.123.x`) — normally the Motive PC. Close the Motive **GUI** first
   (the API takes the cameras).
2. **Install the one dependency** (from source — it's not a clean PyPI package):
   `git clone https://github.com/unitreerobotics/unitree_sdk2_python && cd unitree_sdk2_python && pip install -e .`
   (pulls in the `cyclonedds` bindings; on Windows you also need the native CycloneDDS lib + `CYCLONEDDS_HOME`).
3. **Edit the CONFIG block** at the top of `publish_sportmodestate.py` (it's all right there):

   | Field | What to put |
   |---|---|
   | `MOTIVE_DIR` | Motive install folder (has `lib\NPTrackingToolsx64.dll`) |
   | `CALIBRATION` | path to the `.cal` calibration file **(required)** |
   | `PROFILE` | path to a `.motive` that contains the rigid body *(optional — leave `""` if the body is already in Motive's loaded project)* |
   | `RIGID_BODY` | the rigid-body name, e.g. `h1_2_pelvis` |
   | `DDS_INTERFACE` | the NIC name or IP on the robot's `192.168.123.x` network *(`""` = auto-detect)* |
   | `DDS_DOMAIN` / `OUT_TOPIC` | `0` / `rt/sportmodestate` for the real robot |
   | `AXIS_MAP`, `IMU_OFFSET_M`, `RATE_HZ` | H1-2 defaults — usually leave as-is |

4. **Run:** `python publish_sportmodestate.py` → it prints the live pose and publishes.
   `Ctrl+C` to stop (it releases the cameras).

### Verify
- On the robot-network box: `dds_topic_check.py --topics rt/sportmodestate` → should read
  ARRIVING / finite.
- **Axis check (do once):** move the robot **+1 m forward** → published `x` should rise ~1;
  **lift 0.5 m** → `z` should rise ~0.5. If a sign is wrong, fix `AXIS_MAP` (e.g. `x,y,z`,
  `-x,-z,y`, …) and re-check.

### Prerequisites in Motive (one-time, in the GUI)
The calibration and the rigid body have to exist before the script can use them:
1. Calibrate (or load an existing `.cal`) and set the ground plane.
2. Stick markers on the pelvis, create a rigid body, name it `h1_2_pelvis`.
3. *(Optional)* Save a `.motive` profile and point `PROFILE` at it — otherwise make sure the
   body is in the project Motive auto-loads, and just set `CALIBRATION`.

---

## Optional: the MCP server (agent-driven / remote control)

`server/` contains an **MCP server** that exposes Motive control as tools over HTTP — useful
when you want **Claude (or another agent) to drive Motive remotely**: load calibration, read
markers, create the rigid body, check tracking, all headless from another machine. It's how
this setup was brought up and validated. It is **not required** for the publisher above.

- `server/motive_api.py` — full ctypes binding to `NPTrackingToolsx64.dll`
- `server/motive_mcp_server.py` — FastMCP server (`--selftest` to validate the DLL binding)
- `server/run_server.ps1` — Windows launcher · `.mcp.json` — remote-server registration
- Drive it from another machine with `dds_tools/motive_cli.py` (in the h12 repo).

## Repo layout
```
publish_sportmodestate.py   ← the one-file publisher (start here)
server/                     ← optional MCP server for agent-driven remote control
skills/                     ← Claude Code skills (deploy + workflow)
bridge/optitrack_bridge/    ← earlier standalone-bridge scaffold (reference; will be generalized later)
```

## Notes
- **Accuracy:** `AXIS_MAP` + `IMU_OFFSET_M` are H1-2 defaults; validate the axes with the motion
  test. The published height is exact only when the rigid-body frame is aligned and the offset
  is right — fine for bring-up, tighten later if needed.
- **Network:** keep Tailscale down during DDS runs; the publisher's host must reach
  `192.168.123.x`. In debug mode the robot publishes nothing on `rt/sportmodestate`, so this
  script is what fills it.
