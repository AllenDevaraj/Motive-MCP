# Windows install — publishing `rt/sportmodestate`

> Goal: clone this repo on a Windows box that has Motive, run a few commands, and start
> publishing `rt/sportmodestate`. The only tricky dependency is **CycloneDDS**; this doc
> explains exactly why, and gives one happy path plus two fallbacks.

## TL;DR

From the repo root, in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_windows.ps1
.\.venv\Scripts\python.exe publish_sportmodestate.py
```

That installs python.org **Python 3.10** (if missing), creates `.venv`, installs the SDK +
CycloneDDS from the **official** `0.10.2` wheel, and proves it by publishing `rt/sportmodestate`
once on loopback.

---

## Why Windows needs special handling

The vendored Unitree SDK (`unitree_sdk2_python/setup.py`) hard-pins **`cyclonedds==0.10.2`**.
On Windows, that release of the `cyclonedds` Python binding ships a **prebuilt wheel only for
Python 3.7–3.10**. On Python **3.11/3.12/3.13** there is no wheel, so `pip` downloads the source
tarball and tries to compile the C extension against a CycloneDDS C library that isn't there —
and prints the error you saw:

```
Could not locate cyclonedds. Try to set CYCLONEDDS_HOME or CMAKE_PREFIX_PATH
```

So this was never really a "build" problem — it's a **Python-version** problem. Verified wheel
matrix (from `pypi.org/pypi/cyclonedds/json`):

| `cyclonedds` version | Windows `win_amd64` wheels | `requires_python` | Keeps the pinned 0.10.2 IDL? |
|---|---|---|---|
| 0.9.x, 0.10.2, 0.10.4, **0.10.5** | cp37, cp38, cp39, **cp310** only | `>=3.7` | ✅ (exact / same 0.10.x API) |
| **11.0.1** | cp310, cp311, cp312, cp313 | `>=3.10` | ⚠️ major-version jump — re-validate |

Two consequences:
- **Python 3.10 is the newest interpreter with an official `0.10.2` wheel.** Use it and there's
  no compiler, no `CYCLONEDDS_HOME`, no version bump.
- The only official wheel that covers Python 3.12 is `cyclonedds 11.0.1` — a major-version
  realignment. Its `cyclonedds.idl` API is *statically* compatible, but it would need a publish
  round-trip to trust, so we don't use it.

---

## The three paths

`install_windows.ps1` implements all three. Pick with `-Mode`.

### 1. Recommended — Python 3.10 + official wheel  (`-Mode auto`, the default)
100% official PyPI artifacts, no compiler, keeps the exact pinned version.

```powershell
# one command:
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_windows.ps1
```

Manual equivalent:
```powershell
winget install --id Python.Python.3.10 --architecture x64 --scope user
# open a NEW terminal so the launcher registers, then from the repo root:
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .\unitree_sdk2_python
.\.venv\Scripts\python.exe publish_sportmodestate.py
```
> We call `.\.venv\Scripts\python.exe` directly instead of `Activate.ps1` so the default
> PowerShell execution policy can't block you.

### 2. Keep your Python 3.11/3.12 — community wheel  (`-Mode community`)
Uses a community-built **`0.10.2`** wheel (still the *exact* pinned version, so the vendored IDL
is byte-identical). Trade-off: it's hosted on a third-party GitHub release.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_windows.ps1 -Mode community
```
Manual (Python 3.12 shown; use `cp311` for 3.11) — note **`python`, not `py`**, because the
Microsoft Store Python has no `py` launcher:
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install https://github.com/LY1806620741/cyclonedds-python/releases/download/0.10.2/cyclonedds-0.10.2-cp312-cp312-win_amd64.whl
.\.venv\Scripts\python.exe -m pip install -e .\unitree_sdk2_python   # cyclonedds already satisfied
```

### 3. Build CycloneDDS from source — last resort  (`-Mode native`, run **elevated**)
Only if no prebuilt wheel works. Needs **VS 2022 Build Tools** (C++ workload, which bundles
CMake). The script enters the VS developer shell, clones `eclipse-cyclonedds/cyclonedds` at tag
**`0.10.2`** (must match the binding — a newer tag triggers `fatal error C1083: q_radmin.h`),
builds + installs it, sets `CYCLONEDDS_HOME` + `PATH`, then compiles the binding.

```powershell
# from an ELEVATED PowerShell:
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_windows.ps1 -Mode native
```

---

## Troubleshooting (the traps)

| Symptom | Cause | Fix |
|---|---|---|
| `Could not locate cyclonedds … CYCLONEDDS_HOME` | Python 3.11/3.12/3.13 has no `0.10.2` wheel → source build | Use Python 3.10 (path 1) or the community wheel (path 2) |
| `running scripts is disabled on this system` | PowerShell default execution policy is Restricted | Launch with `powershell -NoProfile -ExecutionPolicy Bypass -File .\install_windows.ps1`; avoid `Activate.ps1` (call `.\.venv\Scripts\python.exe` directly) |
| `py : The term 'py' is not recognized` | Microsoft Store Python has **no `py` launcher** | Use `python` / `python3`, or install python.org Python 3.10 (path 1) |
| `python` opens the Microsoft Store | App Execution Aliases stubs | Settings → Apps → Advanced app settings → App execution aliases → turn off `python.exe`/`python3.exe`; or use the explicit `.\.venv\Scripts\python.exe` |
| Still `Could not locate cyclonedds` on Python 3.10 | 32-bit or ARM interpreter (wheel is `win_amd64`) | Use a **64-bit** Python: `python -c "import struct;print(struct.calcsize('P')*8)"` must print `64` |
| `git`/`py`/`cmake` "not recognized" right after a `winget install` | New PATH/launcher only registers in a **new** process | Open a NEW terminal and re-run (the script refreshes PATH in-session and probes absolute paths) |
| `winget` not found | Old Windows 10 build without App Installer | Install Python 3.10 (x64) and Git from their sites by hand, then re-run |
| native build: `cmake … not recognized` | MSVC/CMake aren't on the global PATH | Run from the **"x64 Native Tools Command Prompt for VS 2022"**, or let `-Mode native` enter the dev shell for you |
| `site-packages is not writeable` | Microsoft Store Python's sandboxed per-user install | Use the python.org / winget build (path 1) |
| smoke test **hangs** | Firewall / NIC discovery, not the install | Allow the Windows Defender Firewall prompt; for a real robot pass the NIC: `ChannelFactoryInitialize(0, "<AdapterName>")` |

---

## Putting the PC on the robot's network

The publisher must run on a machine that's on the robot's DDS subnet (`192.168.123.x`). Two ways:

1. **Wired (most reliable).** A USB-ethernet adapter on the PC → into the robot's onboard
   network switch → static `192.168.123.x` (e.g. `.222`). DDS is happiest on wired.
2. **Robot's WiFi.** Joining the robot's own WiFi hands the PC a `192.168.123.x` address (so it
   *is* on the DDS subnet). Convenient, but DDS **discovery is multicast**, which WiFi can drop
   or block — so after connecting, verify the topic actually arrives (below), don't assume it.

Either way, leave `DDS_INTERFACE = ""` and the publisher auto-detects the `192.168.123.x` IP at
startup. **The interface is chosen at startup — if you switch networks, restart the publisher.**
Unitree's own SDK docs specify **ethernet** for low-level DDS; treat WiFi as best-effort.

## Loopback vs. the real robot

The installer's smoke test calls `ChannelFactoryInitialize(0)` (default/loopback) — it proves
the DDS stack imports and publishes, **not** that the robot is reachable. To confirm the real
path, on a machine on the robot subnet run `dds_topic_check.py` and check `rt/sportmodestate`
shows up next to `rt/lowstate`.

## Version summary (what the installer pins, and why)

- **`cyclonedds`: exactly `0.10.2` on every path** — it's the SDK's hard pin; keeping it
  unchanged keeps `from cyclonedds.idl import …` byte-for-byte identical (zero compat risk).
- **Python: 3.10 (x64, python.org)** for the recommended path — newest interpreter with an
  official `0.10.2` wheel; python.org build avoids the Microsoft Store sandbox.
- **Native fallback C-library tag: `0.10.2`**, `BUILD_IDLC` left ON (the binding's `_idlpy`
  links `cycloneddsidl`), `BUILD_EXAMPLES=OFF`.
