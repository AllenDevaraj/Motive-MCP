---
name: motive-deploy
description: Use when setting up or starting the Motive MCP server on the Windows OptiTrack PC — installing per-user Python, installing dependencies, launching the server, and connecting Claude Code to it over HTTP. Windows/PowerShell steps. Triggers on "deploy the motive server", "install the motive mcp", "start the motive server", "connect to the motive mcp".
---

# Deploying the Motive MCP server (Windows OptiTrack PC)

The server runs on the Windows PC (host `DESKTOP-7BL2VJ1`, user `arpg`). It needs a 64-bit Python
(to match `NPTrackingToolsx64.dll`). The account is **non-admin** — everything below is per-user,
no elevation. Internet is reachable (python.org + pypi confirmed).

## Pre-flight (operator confirms)

- The **Motive GUI is closed** during server runs.
- Shared-machine clearance to install per-user Python, open a TCP port, and run the server.
- The PC's current IP (DHCP; was `192.168.50.44`). Firewall is off, so the port is reachable.

## 1. Install Python (per-user, 64-bit) + deps

```powershell
winget install -e --id Python.Python.3.12 --scope user
# (or python.org installer → "Install for me only", "Add to PATH". Choose 64-bit.)
# new shell, then:
python -c "import struct; print(struct.calcsize('P')*8, 'bit')"   # must print 64
python -m pip install --user --upgrade pip
python -m pip install --user "mcp[cli]"
```

## 2. Copy the server + sanity-check the DLL binding

Copy this plugin's `server/` folder to the PC (e.g. `C:\Users\arpg\motive-mcp\`), then:

```powershell
cd C:\Users\arpg\motive-mcp
python motive_mcp_server.py --selftest      # Motive GUI must be CLOSED
```
Expect: `DLL loaded`, `TT_Initialize OK`, camera count > 0, `PASS`. If it says the system is in
use → the Motive GUI is still open.

## 3. Run the server

```powershell
.\run_server.ps1                 # serves 0.0.0.0:8765, prints  http://<ip>:8765/mcp
```

## 4. Connect Claude Code (laptop, on IRLab)

```bash
claude mcp add --transport http motive http://<motive-pc-ip>:8765/mcp
```
Then the `motive` tools are available; drive them with the **motive-workflow** skill. Verify the
TCP path first if unsure: `nc -vz <motive-pc-ip> 8765`.

Alternatively this plugin ships `.mcp.json` pre-pointed at `192.168.50.44:8765` — edit the IP there
if DHCP moved it (a DHCP reservation for the PC avoids this).

## Teardown

In Claude: call the `shutdown` tool (releases cameras) → stop the server (Ctrl-C) → reopen the
Motive GUI if the lab needs it.

## Notes / risks to verify on first run

- **License/edition:** if `TT_Initialize` fails with a licensing error, this Motive edition may not
  include the API entitlement — report the exact message.
- The API **replaces** the GUI for the session; coordinate with other lab users (shared machine).
- DHCP lease was short — the PC IP can change between sessions; re-check it each time.
