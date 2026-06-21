# mcp-server/ — optional, agent-driven Motive control

**You do not need anything in this folder to stream the robot's pose.** For the normal
flow — install, edit CONFIG, run the publisher — see the [top-level README](../README.md).
Stop here unless you specifically want Claude (or another agent) to drive Motive remotely.

This folder is a self-contained **Claude Code plugin + MCP server** that exposes Motive
control as tools over HTTP: load calibration, create/enable the `h1_2_pelvis` rigid body,
toggle VRPN/NatNet streaming, check tracking — all headless from another machine. It's how
the rig was brought up and validated; it is **not** part of the publisher path.

```
mcp-server/
├── server/
│   ├── motive_api.py          ← ctypes binding to NPTrackingToolsx64.dll
│   ├── motive_mcp_server.py   ← FastMCP server  (python motive_mcp_server.py --selftest)
│   ├── run_server.ps1         ← Windows launcher (serves 0.0.0.0:8765)
│   └── requirements.txt
├── skills/
│   ├── motive-deploy/         ← skill: install + launch the server on the Windows PC
│   └── motive-workflow/       ← skill: the correct tool order to drive Motive
├── .mcp.json                  ← MCP registration (HTTP, edit the IP for your PC)
└── .claude-plugin/plugin.json ← plugin manifest (this folder is the plugin root)
```

## Use it

1. On the Windows OptiTrack PC, run `server/run_server.ps1` (Motive GUI closed). It prints
   `http://<pc-ip>:8765/mcp`. See the **motive-deploy** skill for the per-user Python setup.
2. From your machine: `claude mcp add --transport http motive http://<pc-ip>:8765/mcp`
   (or edit the IP in `.mcp.json`, which is pre-pointed at `192.168.50.44:8765`).
3. Drive it with the **motive-workflow** skill.

To install this as a plugin, point Claude Code's plugin loader at **this `mcp-server/`
directory** (it holds the `.claude-plugin/` manifest), not the repo root.
