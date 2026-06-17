# Recon request — OptiTrack / Motive Windows PC

**To the agent on the Windows PC:** you have zero prior context. We (a separate Claude on a Linux
machine) are scoping an **MCP server** that will let an AI drive the **OptiTrack Motive** app on
*this* Windows PC — to run camera calibration, configure streaming, and define rigid bodies for a
humanoid-robot motion-capture setup. Before we build anything, we need facts about this machine.

**Your task:** run the commands below (PowerShell, mostly read-only), answer the questions, and
write everything into a single file named **`WINDOWS_PC_RECON.md`** (the operator will carry it
back). Paste actual command output; don't summarize away version numbers or paths. If a command
errors or returns nothing, say so explicitly — "not found" is a useful answer.

> Why we care, in one line: the cleanest design wraps Motive's **C/C++ Motive API**
> (`NPTrackingTools` / `MotiveAPI`) in an MCP server. Whether that's possible here depends on the
> Motive version, whether the API SDK is installed, and whether Python + a C++ toolchain exist.
> The fallback (if no API) is GUI automation, which needs different things. So gather all of it.

---

## A. Motive software

```powershell
# Motive version + install path
Get-ChildItem "C:\Program Files\OptiTrack","C:\Program Files (x86)\OptiTrack" -Recurse -Filter "Motive.exe" -ErrorAction SilentlyContinue |
  ForEach-Object { "{0}  v{1}" -f $_.FullName, $_.VersionInfo.ProductVersion }
```
Also report (from the GUI if needed): **Help → About** exact version + **edition**, and the
**license type** (perpetual/subscription; sticker on the monitor if visible).

## B. ★ Motive API / SDK availability (the decisive item)

```powershell
# Headers, libs, DLLs for the Motive API + the NMotive scripting assembly
Get-ChildItem "C:\Program Files\OptiTrack","C:\Program Files (x86)\OptiTrack" -Recurse -ErrorAction SilentlyContinue `
  -Include NPTrackingTools.h,NPTrackingTools.lib,NPTrackingTools.dll,MotiveAPI.h,MotiveAPI.lib,MotiveAPI.dll,NMotiveAPI.chm,NMotive.dll |
  Select-Object FullName,Length,LastWriteTime

# Batch Processor + example scripts (indicates the NMotive/IronPython surface)
Get-ChildItem "C:\Program Files\OptiTrack" -Recurse -ErrorAction SilentlyContinue `
  -Include MotiveBatchProcessor.exe,*.chm | Select-Object FullName

# Is there a separate "Motive API"/SDK/Devkit folder anywhere obvious?
Get-ChildItem "C:\Program Files\OptiTrack","C:\Program Files (x86)\OptiTrack","$env:USERPROFILE\Documents" -Directory -Recurse -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match 'API|SDK|Devkit|NPTracking|NMotive|Sample' } | Select-Object FullName
```
Report: do `NPTrackingTools.h` / `.lib` / `.dll` (or `MotiveAPI.*`) **exist on this machine**?
Full paths + the **bitness** of any DLL (almost certainly 64-bit, but confirm). If none found,
say "Motive API SDK NOT installed here."

## C. Python + build environment

```powershell
python --version 2>$null; py -3 --version 2>$null
python -c "import struct,sys; print('python', sys.version, struct.calcsize('P')*8, 'bit')" 2>$null
where.exe python; where.exe py
pip --version 2>$null

# C/C++ toolchain (needed only if we must build a Python binding to the C++ API)
where.exe cl 2>$null; where.exe msbuild 2>$null
Get-ChildItem "C:\Program Files\Microsoft Visual Studio","C:\Program Files (x86)\Microsoft Visual Studio" -Directory -ErrorAction SilentlyContinue | Select-Object FullName

where.exe git 2>$null
```
Report: Python present? **version + 32/64-bit** (must match the API DLL). Can you `pip install`
packages (internet access / proxy)? Any Visual Studio / Build Tools (MSVC `cl.exe`)?

## D. ★ Network / how the Linux machine will reach this PC

```powershell
ipconfig /all
Get-NetFirewallProfile | Select-Object Name,Enabled
Get-Service sshd -ErrorAction SilentlyContinue | Select-Object Name,Status   # is OpenSSH server present?
```
Report: this PC's **IPv4 address(es), subnet mask, default gateway**, and which network(s) it's on
(is it on the MoCap `192.168.50.x` net? what's its IP — is it `192.168.50.10` or `.24` or
something else?). **Windows Firewall** on/off per profile. Is **OpenSSH server** installed/running?
**Can you open an inbound TCP port** for a local server (admin rights — see F)?

*(Connectivity test — if the operator gives you the Linux laptop's IP on the shared network:)*
```powershell
ping <LINUX_LAPTOP_IP>
```

## E. OptiTrack system state (for the calibration/stream plan)

From the Motive GUI, report:
- **Camera count + model**, and current **frame rate**.
- **Calibration:** is there a current/applied calibration? Its **quality/result** and date if shown.
- **Continuous Calibration:** is it available in this version, and currently on/off?
- **Streaming (Data Streaming pane):** is **VRPN** and/or **NatNet** enabled now? What is the
  **Local Interface** IP set to? Transmission type (Unicast/Multicast)?
- **Assets pane:** list existing **rigid-body names** already saved (so we don't clobber them).
- **Saved profiles/calibration files** on disk:
```powershell
Get-ChildItem "$env:USERPROFILE\Documents\OptiTrack","$env:LOCALAPPDATA\OptiTrack","$env:USERPROFILE" -Recurse -ErrorAction SilentlyContinue `
  -Include *.motive,*.ttp,*.cal,*.mcal,*.tra | Select-Object FullName,LastWriteTime
```

## F. Operating constraints (these pick the architecture)

Answer in prose:
1. **Admin rights?** Run this and report true/false:
   ```powershell
   [bool](([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator))
   ```
   (We need admin to install Python/compiler, open a firewall port, or run a service.)
2. **GUI vs headless:** Is it acceptable for an agent to run a **headless Motive-API program that
   replaces the Motive GUI** during a calibration session (the API owns the cameras, so the GUI
   can't run at the same time)? Or must the lab's **Motive GUI stay the primary interface** (which
   would push us toward slower, more brittle GUI automation instead)?
3. **Shared machine?** Are there usage windows / other users whose calibration or saved assets we
   must not disturb?
4. **Internet access** on this PC for `pip`/downloads? (Or is it air-gapped / proxied?)

---

## What to send back (`WINDOWS_PC_RECON.md`) — checklist
- [ ] Motive **version + edition + license** (A)
- [ ] Motive **API SDK present? paths + bitness** — or "not installed" (B) ← most important
- [ ] **NMotive / Batch Processor** present? (B)
- [ ] **Python** present? version + **32/64-bit** + pip/internet (C)
- [ ] **C++ toolchain** (MSVC) present? (C)
- [ ] **Network:** this PC's IP/subnet/gateway, which net, firewall, SSH, can-open-a-port (D)
- [ ] **OptiTrack state:** cameras, frame rate, calibration, continuous-cal, streaming config,
      existing rigid bodies, saved profiles (E)
- [ ] **Constraints:** admin rights, GUI-vs-headless tolerance, shared-machine windows, internet (F)

If anything is ambiguous, note your uncertainty rather than guessing — we'll follow up.
