# Recon round 2 — confirm the 3 build linchpins (Motive 2.2 MCP plugin)

**To the Windows-PC agent:** round 1 confirmed Motive **2.2.0.1**, no usable Python, no C++ compiler,
non-admin account, firewall off, this PC at `192.168.50.44`. We're building an **MCP server (Python +
ctypes)** that calls Motive's C API DLL to manage rigid bodies + streaming. Three things must be
confirmed/done before we write code. Put results in **`WINDOWS_PC_RECON_2.md`**.

---

## 1. ★ Confirm the Motive API DLL (round 1 used the wrong filename)

Motive ships it as `NPTrackingToolsx64.dll` (the `x64` suffix is why the earlier search missed it).

```powershell
# corrected search — any NPTracking dll/lib anywhere under Motive
Get-ChildItem "C:\Program Files\OptiTrack\Motive" -Recurse -ErrorAction SilentlyContinue -Include *.dll,*.lib |
  Where-Object { $_.Name -match 'NPTracking' } | Select-Object FullName,Length,LastWriteTime
# and just list the lib folder
Get-ChildItem "C:\Program Files\OptiTrack\Motive\lib" -ErrorAction SilentlyContinue | Select-Object Name,Length
```
Report every match (full path + size). If `NPTrackingToolsx64.dll` exists, **that's the linchpin —
ctypes can load it with no compiler.**

## 2. ★ Dump the API surface from the on-disk header

We need the exact `TT_*` functions this 2.2 install exposes (esp. streaming, rigid-body, calibration).

```powershell
# list every TT_ function declaration (the public API)
Select-String -Path "C:\Program Files\OptiTrack\Motive\inc\NPTrackingTools.h" -Pattern "TT_" |
  ForEach-Object { $_.Line.Trim() }
# also list any other headers in inc\
Get-ChildItem "C:\Program Files\OptiTrack\Motive\inc" | Select-Object Name
```
Paste the **full list of `TT_...` lines** (it's ~100-200 lines). This tells us exactly what we can
call: look especially for `TT_StreamVRPN`, `TT_StreamNP`, `TT_LoadProfile`, `TT_LoadCalibration`,
`TT_CreateRigidBody` / rigid-body funcs, `TT_SetFrameRate`, and any `TT_*Calibration*` functions.

## 3. ★ Python + internet (we need a per-user Python; no admin required)

```powershell
# is there a REAL python (not the Store stub at WindowsApps)?
Get-Command python,python3,py -ErrorAction SilentlyContinue | Select-Object Name,Source
# internet reachable for downloads/pip?
Test-NetConnection www.python.org -Port 443 -InformationLevel Quiet
Test-NetConnection pypi.org -Port 443 -InformationLevel Quiet
```
Report: is there a usable Python (path NOT under `…\WindowsApps\`)? Do both `Test-NetConnection`
return **True** (internet OK)?

**If internet is OK and the operator approves**, install Python *per-user* (no admin) and the libs —
this leaves us ready to build:
```powershell
winget install -e --id Python.Python.3.12 --scope user   # OR download python.org installer, "Install for me only", PATH on
# then, in a NEW shell:
python -m pip install --user --upgrade pip
python -m pip install --user "mcp[cli]" fastmcp
python -c "import struct; print('python', struct.calcsize('P')*8, 'bit')"   # MUST be 64-bit to match NPTrackingToolsx64.dll
```
Report the Python version + **bitness (must be 64-bit)** and whether the pip installs succeeded.

---

## 4. Operator decisions (answer in prose)

1. **GUI vs headless:** our app uses Motive's API DLL, which **takes over the cameras** — so the
   **Motive GUI must be closed** while our server runs (and reopened afterward). Is that acceptable
   for dedicated sessions on this shared machine?
2. **Shared-machine etiquette:** this PC has years of other projects' calibrations/assets. Are we
   cleared to (a) install per-user Python, (b) run a server that opens a TCP port, (c) load/create
   rigid bodies and toggle streaming? Any usage windows to respect / people to notify?
3. **Scope check:** the system is already calibrated (Exceptional 0.379 mm). Confirm we only need
   **rigid-body + streaming control** (not automated wand calibration). Yes/no.
4. **Motive edition/license (GUI → Help → About):** report exact edition + license type — some
   editions gate the API.

---

## Send back `WINDOWS_PC_RECON_2.md` with:
- [ ] DLL path(s) for `NPTrackingToolsx64.dll` (+ lib folder listing) — or "not present"
- [ ] Full `TT_*` function list from the header
- [ ] Python: usable real Python? internet True/True? per-user install + pip result + **bitness**
- [ ] Operator answers to the 4 questions
