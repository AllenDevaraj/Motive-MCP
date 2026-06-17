# motive-mocap

A Claude Code plugin that lets Claude control the lab's **OptiTrack Motive 2.2** system — load
calibration, manage rigid bodies, and toggle **VRPN/NatNet streaming** — so the **Unitree H1-2
pelvis pose** can be streamed into the MJPC controller (`rt/sportmodestate`).

## How it works

```
  Linux laptop (IRLab 192.168.50.x)            Windows OptiTrack PC (192.168.50.44)
  ┌───────────────────────────┐   HTTP/MCP    ┌──────────────────────────────────┐
  │ Claude Code  ── motive ───────────────────►│ motive_mcp_server.py (FastMCP)   │
  │ tools (this plugin)        │  :8765/mcp    │   └ ctypes → NPTrackingToolsx64.dll│
  └───────────────────────────┘               │        └ Motive engine + cameras  │
                                              └──────────────────────────────────┘
                              VRPN :3883  →  OptiTrack→DDS bridge (laptop)  →  rt/sportmodestate → MJPC
```

The MCP **server runs on the Windows PC** (it needs the cameras + DLL locally). Claude connects to
it **remotely over HTTP**. The server wraps the Motive 2.2 C API via **ctypes — no compiler needed**.

## Scope (what it does / doesn't)

- ✅ Load calibration (`.cal`) and profiles (`.motive`); manage rigid bodies (add/create/enable);
  set frame rate; **enable VRPN/NatNet streaming**; read live pose + status.
- ⛔ **No wand calibration** — Motive 2.2 doesn't expose it through the API. Calibrate in the GUI,
  export the `.cal`, load it here. (The rig is already calibrated to 0.379 mm.)

## Components

| Path | What |
|---|---|
| `server/motive_api.py` | ctypes binding to `NPTrackingToolsx64.dll` (signatures from the on-disk 2.2 header) |
| `server/motive_mcp_server.py` | FastMCP server exposing the tools over HTTP; `--selftest` mode |
| `server/run_server.ps1` | Windows launcher (closes-GUI pre-flight, prints the connect URL) |
| `.mcp.json` | Registers the remote `motive` HTTP server (edit the IP if DHCP moved it) |
| `skills/motive-deploy` | Windows setup: install Python, run the server, connect Claude |
| `skills/motive-workflow` | Tool sequence + H1-2 rigid-body/frame conventions |

## MCP tools

`initialize` · `status` · `load_calibration` · `load_profile` · `list_rigid_bodies` ·
`load_rigid_bodies` · `create_rigid_body` · `set_rigid_body_enabled` · `rigid_body_pose` ·
`set_frame_rate` · `enable_vrpn` / `disable_vrpn` · `enable_natnet` / `disable_natnet` · `shutdown`

## Prerequisites (Windows PC)

- Motive 2.2 with the API DLL at `C:\Program Files\OptiTrack\Motive\lib\NPTrackingToolsx64.dll` ✓
- 64-bit Python (per-user install, no admin) + `mcp[cli]`
- Motive GUI **closed** while the server runs (the API owns the cameras)

## Install / run

See the **motive-deploy** skill (or `skills/motive-deploy/SKILL.md`). Short version:
1. Per-user Python + `pip install --user "mcp[cli]"`.
2. Copy `server/` to the PC → `python motive_mcp_server.py --selftest`.
3. `.\run_server.ps1` → note the printed `http://<ip>:8765/mcp`.
4. Laptop: `claude mcp add --transport http motive http://<ip>:8765/mcp`.

## ✅ Status: hardware-validated (selftest PASS, 2026-06-17)

`--selftest` **PASSED on the lab's OptiTrack PC**: DLL loaded (build 48012), `TT_Initialize` OK,
**5× Prime 17W @ 360 Hz** enumerated (#32710–32716), 38 existing rigid bodies listed. The
ctypes↔DLL binding and engine init are confirmed on the real system. The Qt platform-plugin path is
auto-resolved — on this install it lives at `…\Motive\assemblies\x64\platforms`.

Still unverified end-to-end: the running HTTP server + live tool calls, VRPN/NatNet streaming
reachability on the IRLab interface, and the OptiTrack→DDS bridge. Next: run the server and connect.

## Operator gates (confirm before first deploy)

1. Closing the Motive GUI during server sessions is acceptable.
2. Clearance to install per-user Python + run a server on the shared ARPG machine.
3. Scope = rigid-body + streaming control (no automated wanding). 
4. Motive edition/license includes the API (verify if `TT_Initialize` returns a license error).

## Security

No credentials. The server exposes camera/streaming control on a LAN port — the Windows firewall is
currently off, so anyone on IRLab could reach it. For a shared lab, prefer binding to a specific
interface or adding a firewall rule scoped to the laptop's IP once it's in regular use.
