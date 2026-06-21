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
2. **Install the Python env (one command).** The SDK's only tricky dependency is CycloneDDS.
   From the repo root, in PowerShell:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\install_windows.ps1
   ```
   This installs Python 3.10 (if missing), makes a `.venv`, installs the vendored
   `unitree_sdk2_python` + CycloneDDS from the official `0.10.2` wheel, and smoke-tests a
   publish. **See [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md)** for what it does, the manual steps,
   the `-Mode community` (keep your Python 3.11/3.12) and `-Mode native` fallbacks, and
   troubleshooting. *(Why a script: `cyclonedds==0.10.2` has no Windows wheel for Python 3.11+,
   so a plain `pip install` on Store Python 3.12 fails — the script picks an interpreter that
   has a prebuilt wheel.)*
3. **Edit the CONFIG block** at the top of `publish_sportmodestate.py` (it's all right there):

   | Field | What to put |
   |---|---|
   | `MOTIVE_DIR` | Motive install folder (has `lib\NPTrackingToolsx64.dll`) |
   | `CALIBRATION` | path to the `.cal` calibration file **(required)** |
   | `PROFILE` | path to a `.motive` that contains the rigid body *(optional — leave `""` if the body is already in Motive's loaded project)* |
   | `RIGID_BODY` | the rigid-body name, e.g. `h1_2_pelvis` |
   | `DDS_INTERFACE` | the NIC name or IP on the robot's `192.168.123.x` network *(`""` = auto-detect)* |
   | `DDS_DOMAIN` / `OUT_TOPIC` | `0` / `rt/sportmodestate` for the real robot |
   | `UDP_SINK` | `""` for direct DDS; `"<bridge-ip>:9870"` for the WiFi/UDP-bridge mode (see **Network setup**) |
   | `AXIS_MAP`, `IMU_OFFSET_M` | H1-2 frame defaults — usually leave as-is |
   | `RATE_HZ` | publish rate, default `200` (cameras run 360 Hz; drop to `100` if the PC can't sustain it) |

4. **Run:** `.\.venv\Scripts\python.exe publish_sportmodestate.py` → it prints the live pose
   and publishes. `Ctrl+C` to stop (it releases the cameras).

### Verify
- On the robot-network box: `dds_topic_check.py --topics rt/sportmodestate` → should read
  ARRIVING / finite.
- **Axis check (do once):** move the robot **+1 m forward** → published `x` should rise ~1;
  **lift 0.5 m** → `z` should rise ~0.5. If a sign is wrong, fix `AXIS_MAP` (e.g. `x,y,z`,
  `-x,-z,y`, …) and re-check.

### Network setup — which device on which network

The robot's real-time DDS (`rt/lowstate`, `rt/lowcmd` ~500 Hz, and the `rt/sportmodestate` slot
we fill) lives on the robot's **wired `192.168.123.x`** network (its onboard switch). That's the
bus the MJPC controller reads, so `rt/sportmodestate` has to land there.

| Device | Network(s) | Runs |
|---|---|---|
| **Robot** | wired `192.168.123.x` (onboard switch) | publishes `lowstate`/`lowcmd`; `sportmodestate` is silent in debug mode |
| **Motive PC** | a route to `192.168.123.x` — a wired NIC into the robot switch, **or** the robot's own WiFi (it hands out a `192.168.123.x` IP); **plus** the camera net (`169.254.x`, wired to the cameras) | Motive + `publish_sportmodestate.py` |
| **Bridge / controller box** (e.g. the laptop) | **wired** `192.168.123.x` into the robot switch (+ WiFi for reaching the PC) | `pose_udp_bridge.py` + the MJPC node *(bridge mode only)* |

**Two ways to run, by how the Motive PC reaches the robot net:**

- **Direct DDS (preferred).** The Motive PC has a **wired** NIC on `192.168.123.x` (a USB-ethernet
  adapter into the robot's switch). `publish_sportmodestate.py` publishes DDS straight on the wire.
  Leave `DDS_INTERFACE=""` (auto-detect) and `UDP_SINK=""`. No bridge needed.

- **UDP bridge (when the PC reaches the robot only over WiFi).** DDS discovery is **multicast**,
  which WiFi APs block — so direct DDS won't cross WiFi (verified on both the lab WiFi and the
  robot's own WiFi). **Unicast** does cross, so route the pose over UDP to a box that's **wired**
  to the robot net, and let that box put it on DDS:
  1. On the Motive PC, set `UDP_SINK = "<bridge-ip>:9870"` (the wired box's `192.168.123.x` IP).
  2. On the wired box, run `python pose_udp_bridge.py --iface <robot-net-NIC> --port 9870`.

  The PC and the bridge box only need to reach each other by **unicast** (same WiFi, or via the
  robot's WiFi↔wired bridge); the bridge box must be **wired** to `192.168.123.x`.

  ```
  Motive PC (WiFi)  ──unicast UDP──►  pose_udp_bridge.py (wired 192.168.123.x)  ──DDS──►  rt/sportmodestate
  ```

### Prerequisites in Motive (one-time, in the GUI)
The calibration and the rigid body have to exist before the script can use them:
1. Calibrate (or load an existing `.cal`) and set the ground plane.
2. Stick markers on the pelvis, create a rigid body, name it `h1_2_pelvis`.
3. *(Optional)* Save a `.motive` profile and point `PROFILE` at it — otherwise make sure the
   body is in the project Motive auto-loads, and just set `CALIBRATION`.

---

## Optional: agent-driven control (`mcp-server/`)

Everything needed to stream the pose is above — you can ignore this section. If you *also*
want **Claude (or another agent) to drive Motive remotely** (load calibration, create the
rigid body, toggle streaming, check tracking, all headless), that lives entirely in
**[`mcp-server/`](mcp-server/)** — a self-contained Claude Code plugin + MCP server. It's
optional and fully separate from the publisher path; see
[`mcp-server/README.md`](mcp-server/README.md).

## Repo layout
```
publish_sportmodestate.py   ← the one-file publisher (start here; runs on the Motive PC)
pose_udp_bridge.py          ← UDP→DDS bridge for WiFi mode (runs on the box wired to the robot)
install_windows.ps1         ← one-command Windows install (Python 3.10 + CycloneDDS + SDK)
unitree_sdk2_python/        ← vendored Unitree SDK (the installer installs this for you)
mcp-server/                 ← OPTIONAL agent-driven Motive control (ignore for the basic flow)
```

## Notes
- **Accuracy:** `AXIS_MAP` + `IMU_OFFSET_M` are H1-2 defaults; validate the axes with the motion
  test. The published height is exact only when the rigid-body frame is aligned and the offset
  is right — fine for bring-up, tighten later if needed.
- **Network:** keep Tailscale down during DDS runs. The publisher's host must reach the robot's
  `192.168.123.x` net (see **Network setup**). DDS does **not** cross WiFi (discovery is multicast,
  which APs block) — if the Motive PC is on WiFi, use the `UDP_SINK` + `pose_udp_bridge.py` path.
  In debug mode the robot publishes nothing on `rt/sportmodestate`, so this script fills it.
