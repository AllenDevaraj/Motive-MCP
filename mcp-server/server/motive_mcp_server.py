"""Motive MCP server — exposes OptiTrack Motive 2.2 control as MCP tools over HTTP.

Runs ON THE WINDOWS MOTIVE PC (it needs the cameras + NPTrackingToolsx64.dll locally).
The Motive GUI must be CLOSED while this runs (the API takes ownership of the cameras).

From the Linux/laptop side, connect Claude Code to it:
    claude mcp add --transport http motive http://<this-pc-ip>:8765/mcp

Validate the DLL binding without streaming (run on the PC):
    python motive_mcp_server.py --selftest

UNTESTED on the machine it was written on — first run on the PC is the real validation.
"""
from __future__ import annotations

import argparse
import sys
import threading
import time

from motive_api import MotiveAPI, MotiveError, DEFAULT_MOTIVE_DIR

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # fall back to the standalone package
    from fastmcp import FastMCP

# --- shared state (single Motive engine, serialized access) ---------------------------------
_lock = threading.RLock()
_api: MotiveAPI | None = None
_motive_dir: str = DEFAULT_MOTIVE_DIR
_running = False
_updater: threading.Thread | None = None

mcp = FastMCP("motive")


def _update_loop() -> None:
    # The Motive engine processes camera frames and drives VRPN/NatNet streaming only while
    # TT_Update() is called. Keep it ticking while the engine is up.
    while _running:
        try:
            with _lock:
                if _api is not None:
                    _api.update()
        except Exception:
            pass
        time.sleep(0.002)  # ~500 Hz attempts; TT_Update consumes whatever frames are ready


def _require() -> MotiveAPI:
    if _api is None:
        raise MotiveError("Motive engine not initialized — call initialize() first.")
    return _api


# --- tools ----------------------------------------------------------------------------------
@mcp.tool()
def initialize(calibration_path: str = "", profile_path: str = "") -> dict:
    """Initialize the Motive engine and take ownership of the cameras (the Motive GUI must be
    closed first). Optionally load a calibration (.cal) and/or a profile (.motive), then start
    the frame-update loop. Returns camera count + build number."""
    global _api, _running, _updater
    with _lock:
        if _api is None:
            _api = MotiveAPI(motive_dir=_motive_dir)
        _api.initialize()
        if profile_path:
            _api.load_profile(profile_path)
        if calibration_path:
            _api.load_calibration(calibration_path)
        if not _running:
            _running = True
            _updater = threading.Thread(target=_update_loop, name="tt-update", daemon=True)
            _updater.start()
        return {"ok": True, "build": _api.build_number(), "cameras": _api.camera_count()}


@mcp.tool()
def status() -> dict:
    """Report engine state: initialized?, build, camera count + frame rate, and every rigid body
    (name, enabled, tracked, mean error in mm). The H1-2 base body should read tracked=true."""
    with _lock:
        if _api is None:
            return {"initialized": False}
        rbs = []
        for i in range(_api.rigid_body_count()):
            rbs.append({
                "index": i,
                "name": _api.rigid_body_name(i),
                "enabled": _api.is_enabled(i),
                "tracked": _api.is_tracked(i),
                "mean_error_mm": round(_api.mean_error(i) * 1000.0, 3),
            })
        cams = _api.camera_count()
        return {
            "initialized": True,
            "build": _api.build_number(),
            "cameras": cams,
            "frame_rate_hz": _api.camera_frame_rate(0) if cams else None,
            "rigid_bodies": rbs,
        }


@mcp.tool()
def load_calibration(path: str) -> dict:
    """Load a camera calibration (.cal) exported from the Motive GUI. Note: Motive 2.2 cannot
    perform wand calibration through the API — calibrate in the GUI, export the .cal, load it here.
    A recent good one on this PC: 'Calibration Exceptional (MeanErr 0.379 mm) 2026-02-17 4.cal'."""
    with _lock:
        _require().load_calibration(path)
        return {"ok": True, "loaded": path}


@mcp.tool()
def load_profile(path: str) -> dict:
    """Load a Motive user profile (.motive) — restores camera settings, rigid bodies, and
    streaming configuration in one shot."""
    with _lock:
        _require().load_profile(path)
        return {"ok": True, "loaded": path}


@mcp.tool()
def list_rigid_bodies() -> dict:
    """List all rigid bodies with index, name, enabled, tracked, and mean error (mm)."""
    return status()


@mcp.tool()
def load_rigid_bodies(path: str, replace: bool = False) -> dict:
    """Load rigid-body definitions from a .tra/.motive file. replace=False ADDS them (keeps other
    users' bodies); replace=True clears the list first. Prefer add to avoid clobbering lab assets."""
    with _lock:
        api = _require()
        if replace:
            api.load_rigid_bodies(path)
        else:
            api.add_rigid_bodies(path)
        return {"ok": True, "loaded": path, "replaced": replace, "count": api.rigid_body_count()}


@mcp.tool()
def create_rigid_body(name: str, marker_xyz_m: list[float], rb_id: int = 1) -> dict:
    """Create a rigid body from marker positions (flat [x,y,z, x,y,z, ...] in METERS, relative to
    the desired pivot). For the H1-2, place the pivot at the pelvis IMU site so the published pose
    matches the controller's expectation (see the motive-workflow skill)."""
    with _lock:
        api = _require()
        api.create_rigid_body(name, rb_id, marker_xyz_m)
        return {"ok": True, "name": name, "count": api.rigid_body_count()}


@mcp.tool()
def list_markers() -> dict:
    """List every reconstructed 3D marker in the current frame (x,y,z meters, Motive world frame,
    which is Y-up — Y is height). Call this BEFORE create_rigid_body_from_markers to confirm only the
    intended markers (e.g. the H1-2 pelvis cluster) are present, and to read their height band so you
    can isolate one cluster when other markers are in the volume."""
    with _lock:
        api = _require()
        api.update()  # pull a fresh frame so the marker list is current
        ms = api.frame_markers()
        ys = [m[1] for m in ms]
        return {"count": len(ms),
                "markers": [{"x": round(x, 4), "y": round(y, 4), "z": round(z, 4)} for (x, y, z) in ms],
                "y_height_range": [round(min(ys), 4), round(max(ys), 4)] if ms else None}


@mcp.tool()
def create_rigid_body_from_markers(name: str, rb_id: int = 1,
                                   y_min: float = -1e9, y_max: float = 1e9) -> dict:
    """Create a rigid body from the CURRENTLY VISIBLE reconstructed markers, pivot at their centroid.
    Optionally restrict to markers within a Motive-Y (height) band [y_min, y_max] to isolate one
    cluster (e.g. the pelvis) when other markers share the volume. For the H1-2 the bridge applies the
    pelvis->IMU offset, so a centroid pivot is fine. Run list_markers() first to pick the band. Returns
    the markers used + centroid (sanity-check the centroid height before trusting it)."""
    with _lock:
        api = _require()
        api.update()
        allm = api.frame_markers()
        used = [m for m in allm if y_min <= m[1] <= y_max]
        if len(used) < 3:
            raise MotiveError(f"need >=3 markers to define a rigid body; found {len(used)} in "
                              f"y in [{y_min}, {y_max}] (total visible {len(allm)})")
        cx = sum(m[0] for m in used) / len(used)
        cy = sum(m[1] for m in used) / len(used)
        cz = sum(m[2] for m in used) / len(used)
        offsets = []
        for (x, y, z) in used:
            offsets += [x - cx, y - cy, z - cz]   # marker positions relative to the pivot (centroid)
        api.create_rigid_body(name, rb_id, offsets)
        return {"ok": True, "name": name, "markers_used": len(used), "total_visible": len(allm),
                "centroid": {"x": round(cx, 4), "y": round(cy, 4), "z": round(cz, 4)},
                "count": api.rigid_body_count()}


@mcp.tool()
def set_rigid_body_enabled(name_or_index: str, enabled: bool = True) -> dict:
    """Enable/disable tracking of a rigid body by name or index."""
    with _lock:
        api = _require()
        i = int(name_or_index) if name_or_index.lstrip("-").isdigit() else api.rigid_body_index(name_or_index)
        if i < 0 or i >= api.rigid_body_count():
            raise MotiveError(f"rigid body not found: {name_or_index}")
        api.set_enabled(i, enabled)
        return {"ok": True, "index": i, "name": api.rigid_body_name(i), "enabled": enabled}


@mcp.tool()
def rigid_body_pose(name_or_index: str) -> dict:
    """Return the live 6-DoF pose of a rigid body: position (x,y,z meters), quaternion, and
    yaw/pitch/roll, plus tracked flag and mean error (mm). Use this to sanity-check the H1-2 pelvis
    (e.g. standing z ≈ height of the tracked point above the floor)."""
    with _lock:
        api = _require()
        i = int(name_or_index) if name_or_index.lstrip("-").isdigit() else api.rigid_body_index(name_or_index)
        if i < 0 or i >= api.rigid_body_count():
            raise MotiveError(f"rigid body not found: {name_or_index}")
        pose = api.rigid_body_location(i)
        pose.update({"name": api.rigid_body_name(i), "tracked": api.is_tracked(i),
                     "mean_error_mm": round(api.mean_error(i) * 1000.0, 3)})
        return pose


@mcp.tool()
def set_frame_rate(hz: int) -> dict:
    """Set the camera system frame rate (Hz) across all cameras. 100-360 Hz typical; the MJPC
    planner runs ~50-65 Hz so any of these is plenty."""
    with _lock:
        ok = _require().set_frame_rate(hz)
        return {"ok": bool(ok), "frame_rate_hz": hz}


@mcp.tool()
def enable_vrpn(port: int = 3883) -> dict:
    """Enable VRPN streaming on the given TCP port (3883 is the lab default). Our Linux-side
    bridge subscribes 'h1_2_pelvis@tcp://<this-pc-ip>:3883' and republishes rt/sportmodestate."""
    with _lock:
        _require().stream_vrpn(True, port)
        return {"ok": True, "vrpn": True, "port": port}


@mcp.tool()
def disable_vrpn(port: int = 3883) -> dict:
    """Disable VRPN streaming."""
    with _lock:
        _require().stream_vrpn(False, port)
        return {"ok": True, "vrpn": False}


@mcp.tool()
def enable_natnet() -> dict:
    """Enable NatNet (NaturalPoint) streaming."""
    with _lock:
        _require().stream_natnet(True)
        return {"ok": True, "natnet": True}


@mcp.tool()
def disable_natnet() -> dict:
    """Disable NatNet streaming."""
    with _lock:
        _require().stream_natnet(False)
        return {"ok": True, "natnet": False}


@mcp.tool()
def shutdown() -> dict:
    """Stop the update loop and release the cameras (TT_Shutdown). Run this before reopening the
    Motive GUI."""
    global _api, _running
    with _lock:
        _running = False
        if _api is not None:
            _api.shutdown()
            _api = None
        return {"ok": True}


# --- entrypoint -----------------------------------------------------------------------------
def _selftest(motive_dir: str) -> int:
    print("[selftest] loading NPTrackingToolsx64.dll ...")
    api = MotiveAPI(motive_dir=motive_dir)
    print(f"[selftest] DLL loaded. build={api.build_number()}")
    if api.qt_platform_path:
        print(f"[selftest] Qt platform plugin dir: {api.qt_platform_path}")
    else:
        print("[selftest] WARNING: qwindows.dll not found under the Motive dir — "
              "Qt init will likely fail. Pass --motive-dir to the real install path.")
    print("[selftest] TT_Initialize() (Motive GUI must be closed) ...")
    try:
        api.initialize()
    except MotiveError as e:
        print(f"[selftest] FAILED: {e}")
        print("[selftest] If this says the system is in use, close the Motive GUI and retry.")
        return 1
    try:
        n = api.camera_count()
        print(f"[selftest] OK — {n} camera(s) detected.")
        for i in range(n):
            print(f"           camera[{i}] = {api.camera_name(i)} @ {api.camera_frame_rate(i)} Hz")
        print(f"[selftest] rigid bodies: {api.rigid_body_count()}")
    finally:
        api.shutdown()
    print("[selftest] PASS — engine init + camera enumeration succeeded.")
    return 0


def main() -> int:
    global _motive_dir
    ap = argparse.ArgumentParser(description="OptiTrack Motive 2.2 MCP server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--motive-dir", default=DEFAULT_MOTIVE_DIR)
    ap.add_argument("--transport", default="streamable-http",
                    choices=["streamable-http", "sse", "stdio"])
    ap.add_argument("--selftest", action="store_true",
                    help="load the DLL, init the engine, list cameras, exit (no MCP serving)")
    ap.add_argument("--allowed-host", action="append", default=[],
                    help="Host header value to allow, e.g. 192.168.50.44:8765 (repeatable). If set, "
                         "DNS-rebinding protection stays ON and only these hosts pass. Default: "
                         "protection OFF for the trusted LAN (fixes 421 'Invalid Host header').")
    args = ap.parse_args()
    _motive_dir = args.motive_dir

    if args.selftest:
        return _selftest(args.motive_dir)

    mcp.settings.host = args.host
    mcp.settings.port = args.port

    # The MCP streamable-http transport blocks non-localhost Host headers by default (DNS-rebinding
    # protection) -> '421 Invalid Host header' when connecting by LAN IP. Relax it for our trusted,
    # firewall-off lab LAN. With --allowed-host, keep protection on and whitelist instead.
    try:
        from mcp.server.transport_security import TransportSecuritySettings
        if args.allowed_host:
            sec = TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                            allowed_hosts=args.allowed_host,
                                            allowed_origins=["*"])
            print(f"[motive-mcp] DNS-rebinding protection ON; allowed hosts: {args.allowed_host}")
        else:
            sec = TransportSecuritySettings(enable_dns_rebinding_protection=False)
            print("[motive-mcp] DNS-rebinding protection OFF (trusted LAN) — any Host header accepted")
        mcp.settings.transport_security = sec
    except Exception as e:
        print(f"[motive-mcp] WARNING: could not set transport security ({e}); "
              "if you get 421 'Invalid Host header', upgrade the 'mcp' package.")

    print(f"[motive-mcp] serving {args.transport} on {args.host}:{args.port}/mcp "
          f"(motive_dir={args.motive_dir})", flush=True)
    mcp.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    sys.exit(main())
