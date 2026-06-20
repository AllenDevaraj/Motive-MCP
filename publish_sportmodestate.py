#!/usr/bin/env python3
r"""
publish_sportmodestate.py  --  ONE-FILE OptiTrack -> Unitree H1-2 base publisher.

WHAT IT DOES
    Reads the H1-2 pelvis rigid body straight from Motive (NPTrackingTools DLL),
    converts the pose into the robot world frame, finite-differences a velocity,
    and publishes it on DDS as  rt/sportmodestate  (unitree_go SportModeState_).
    That is the whole job. No MCP, no laptop bridge, no extra processes.

WHERE TO RUN IT
    On a machine that has BOTH:
      (1) Motive installed (the NPTrackingToolsx64.dll + the cameras), AND
      (2) a route to the robot's DDS network (192.168.123.x) -- via a wired ethernet link
          into the robot's onboard switch, OR by joining the robot's own WiFi (it hands the
          PC a 192.168.123.x address). Either way the PC ends up on the DDS subnet.
    Normally that is the Motive PC, with the robot reachable from it. NOTE: the network
    interface is chosen at STARTUP, so if you change networks, RESTART this script.
    The Motive GUI must be CLOSED while this runs (the API takes the cameras).

HOW TO RUN IT
    1) Install unitree_sdk2py FROM SOURCE (it is not a clean PyPI package):
         git clone https://github.com/unitreerobotics/unitree_sdk2_python
         cd unitree_sdk2_python && pip install -e .
       It pulls in the `cyclonedds` python bindings, which need the native CycloneDDS
       library on Windows (set CYCLONEDDS_HOME). This is the only third-party dependency.
    2) Edit the CONFIG block below (paths + rigid-body name + robot network).
    3) python publish_sportmodestate.py
    Ctrl+C to stop (it releases the cameras on exit).

NOTE ON ACCURACY
    Frame (AXIS_MAP) and the pelvis->IMU offset are H1-2 defaults. Validate the
    axes once with a motion test (move the robot +1 m forward -> world x +1; lift
    0.5 m -> world z +0.5) and adjust AXIS_MAP if a sign is wrong.

NOTE ON GLITCHES
    A single bad rigid-body solve (marker swap/occlusion) can pop the pose a few cm
    for ONE frame; finite-differenced, that is a phantom 1-5 m/s velocity spike on the
    wire -- which a balance controller would chase as real motion. The OUTLIER GATE
    (CONFIG block) rejects such frames and re-publishes the last good pose instead.
    Measured on the real H1-2: ~6 such pops/min; with the gate on they never reach the
    controller. A jump sustained past OUTLIER_HOLD_MAX frames is taken as real motion
    and accepted, so the gate can never freeze the feed.
"""

# ==========================================================================================
#  CONFIG  --  EDIT THIS BLOCK, THEN RUN.  (everything you need is right here)
# ==========================================================================================
CONFIG = {
    # ---- MOTIVE (this PC) -------------------------------------------------------------
    "MOTIVE_DIR":   r"C:\Program Files\OptiTrack\Motive",
    #   ^ Motive install folder. Must contain  lib\NPTrackingToolsx64.dll

    "CALIBRATION":  r"C:\Users\arpg\Desktop\Calibration Exceptional (MeanErr 0.379 mm) 2026-02-17 4.cal",
    #   ^ REQUIRED. The .cal camera calibration to load.

    "PROFILE":      r"",
    #   ^ OPTIONAL .motive profile that CONTAINS the rigid body. Leave "" if the
    #     rigid body already lives in Motive's auto-loaded project (as on this PC).
    #     If the script can't find RIGID_BODY, point this at a profile that has it.

    "RIGID_BODY":   "h1_2_pelvis",
    #   ^ Name of the rigid body to track (exact match).

    # ---- ROBOT DDS OUTPUT -------------------------------------------------------------
    "DDS_INTERFACE": "",
    #   ^ The NIC on the robot's network, as an IP (recommended, esp. on Windows, e.g.
    #     "192.168.123.222") or a Linux interface name (e.g. "enp3s0").
    #     Leave "" to auto-detect this machine's 192.168.123.x IP (and WARN if there's no
    #     route to the robot). This machine MUST be able to reach 192.168.123.x -- via a
    #     wired link to the robot, or by joining the robot's WiFi (gives a 192.168.123.x IP).
    #     The interface is picked at STARTUP, so if you switch networks, RESTART this script.

    "DDS_DOMAIN":   0,            # robot DDS domain (0 for the real H1-2)
    "OUT_TOPIC":    "rt/sportmodestate",

    "UDP_SINK":     "",
    #   ^ OPTIONAL no-wire fallback. If this PC can only reach the robot over WiFi, DDS won't
    #     get through (DDS discovery is multicast, which WiFi APs block). Set this to
    #     "<laptop-ip>:<port>" (e.g. "192.168.123.4:9870") and the pose is ALSO sent there by
    #     unicast UDP, which DOES cross WiFi. Run dds_tools/pose_udp_bridge.py on that laptop
    #     (it's on the robot's WIRED net) to put it on DDS next to lowstate. Leave "" for the
    #     normal direct-DDS path (preferred -- wire this PC to the robot instead).

    # ---- H1-2 FRAME / OFFSET (correct H1-2 defaults; usually leave as-is) --------------
    "AXIS_MAP":      "x,-z,y",
    #   ^ Motive is Y-up; the robot world is Z-up, floor z=0, +x forward.
    #     "x,-z,y" means  world=(motive_x, -motive_z, motive_y).
    #     Use "x,y,z" if Motive is already streaming Z-up. VALIDATE with the motion test.

    "IMU_OFFSET_M":  (-0.04452, -0.01891, 0.27756),
    #   ^ pelvis-origin -> IMU site, in the pelvis body frame (matches the controller).
    #     Set to (0, 0, 0) if the rigid-body PIVOT was placed AT the IMU site.

    "RATE_HZ":       200,         # publish rate Hz (cameras run 360Hz; timeBeginPeriod(1) lets the
    #                               Windows pacer hit ~200Hz. Drop to 100 if your box can't sustain it.)
    "VEL_LOWPASS_MS": 30,         # velocity low-pass time constant (ms)

    # ---- OUTLIER GATE (drop glitchy rigid-body solves -- see NOTE ON GLITCHES above) ----
    "OUTLIER_MAX_SPEED":  2.0,    # reject a frame whose implied base speed exceeds this (m/s); 0 = off.
    #                               A 1-frame solve glitch implies many m/s; real base motion is < ~1 m/s.
    "OUTLIER_MAX_ERR_MM": 0.0,    # ALSO reject if the rigid-body mean error exceeds this (mm); 0 = off.
    #                               Secondary check (the speed gate is primary); cal baseline ~0.38 mm.
    "OUTLIER_HOLD_MAX":   5,      # after this many CONSECUTIVE rejects, accept anyway + reset velocity
    #                               (a sustained jump = real motion / teleport, not a 1-frame glitch).
}
# ==========================================================================================
#  END CONFIG  --  you shouldn't need to edit anything below this line.
# ==========================================================================================

import ctypes
import math
import os
import sys
import time

NPRESULT_SUCCESS = 0


# ------------------------------------------------------------------------------------------
#  Motive reader  (embedded ctypes binding to NPTrackingTools 2.2 -- no compiler needed)
# ------------------------------------------------------------------------------------------
class MotiveError(RuntimeError):
    pass


def _setup_qt_platform(motive_dir):
    """Point Qt at Motive's bundled 'platforms' plugin (qwindows.dll), else TT_Initialize
    fails with 'could not find or load the Qt platform plugin "windows"'."""
    plat = None
    for d in (os.path.join(motive_dir, "platforms"), os.path.join(motive_dir, "lib", "platforms")):
        if os.path.isfile(os.path.join(d, "qwindows.dll")):
            plat = d
            break
    if plat is None and os.path.isdir(motive_dir):
        for base, _dirs, files in os.walk(motive_dir):
            if "qwindows.dll" in files:
                plat = base
                break
    if plat:
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plat
        os.environ.setdefault("QT_PLUGIN_PATH", os.path.dirname(plat))
    return plat


class Motive:
    def __init__(self, motive_dir):
        dll = os.path.join(motive_dir, "lib", "NPTrackingToolsx64.dll")
        if not os.path.isfile(dll):
            raise MotiveError(f"NPTrackingToolsx64.dll not found at {dll} -- check MOTIVE_DIR")
        for d in (motive_dir, os.path.join(motive_dir, "lib")):
            if os.path.isdir(d):
                try:
                    os.add_dll_directory(d)
                except (AttributeError, OSError):
                    pass
        os.environ["PATH"] = motive_dir + os.pathsep + os.environ.get("PATH", "")
        _setup_qt_platform(motive_dir)
        self.lib = ctypes.CDLL(dll)
        self._declare()

    def _declare(self):
        L, c = self.lib, ctypes
        for fn in ("TT_Initialize", "TT_Shutdown", "TT_Update", "TT_BuildNumber"):
            getattr(L, fn).restype = c.c_int
        L.TT_GetResultString.restype = c.c_char_p
        L.TT_GetResultString.argtypes = [c.c_int]
        for fn in ("TT_LoadProfile", "TT_LoadCalibration"):
            f = getattr(L, fn); f.restype = c.c_int; f.argtypes = [c.c_char_p]
        L.TT_CameraCount.restype = c.c_int
        L.TT_RigidBodyCount.restype = c.c_int
        L.TT_RigidBodyName.restype = c.c_char_p
        L.TT_RigidBodyName.argtypes = [c.c_int]
        L.TT_IsRigidBodyTracked.restype = c.c_bool
        L.TT_IsRigidBodyTracked.argtypes = [c.c_int]
        L.TT_RigidBodyMeanError.restype = c.c_float
        L.TT_RigidBodyMeanError.argtypes = [c.c_int]
        # void TT_RigidBodyLocation(int, float* x,y,z, qx,qy,qz,qw, yaw,pitch,roll)
        L.TT_RigidBodyLocation.argtypes = [c.c_int] + [c.POINTER(c.c_float)] * 10

    def _check(self, code, what):
        if code != NPRESULT_SUCCESS:
            raw = self.lib.TT_GetResultString(code)
            msg = raw.decode(errors="replace") if raw else f"NPRESULT {code}"
            raise MotiveError(f"{what} failed: {msg} (code {code})")

    def initialize(self):
        self._check(self.lib.TT_Initialize(), "TT_Initialize")

    def shutdown(self):
        try:
            self.lib.TT_Shutdown()
        except Exception:
            pass

    def update(self):
        self.lib.TT_Update()

    def build_number(self):
        return int(self.lib.TT_BuildNumber())

    def camera_count(self):
        return int(self.lib.TT_CameraCount())

    def load_calibration(self, path):
        self._check(self.lib.TT_LoadCalibration(path.encode()), f"TT_LoadCalibration({path})")

    def load_profile(self, path):
        self._check(self.lib.TT_LoadProfile(path.encode()), f"TT_LoadProfile({path})")

    def rigid_body_count(self):
        return int(self.lib.TT_RigidBodyCount())

    def rigid_body_name(self, i):
        n = self.lib.TT_RigidBodyName(i)
        return n.decode(errors="replace") if n else f"rb{i}"

    def rigid_body_index(self, name):
        for i in range(self.rigid_body_count()):
            if self.rigid_body_name(i) == name:
                return i
        return -1

    def is_tracked(self, i):
        return bool(self.lib.TT_IsRigidBodyTracked(i))

    def mean_error_mm(self, i):
        return float(self.lib.TT_RigidBodyMeanError(i)) * 1000.0

    def location(self, i):
        """Return (pos[x,y,z], quat_wxyz) in Motive world frame, meters."""
        v = [ctypes.c_float(0.0) for _ in range(10)]
        self.lib.TT_RigidBodyLocation(i, *[ctypes.byref(x) for x in v])
        x, y, z, qx, qy, qz, qw, _yaw, _pitch, _roll = (a.value for a in v)
        return (x, y, z), (qw, qx, qy, qz)


# ------------------------------------------------------------------------------------------
#  Math: Motive frame -> robot world (pure Python, no numpy)
# ------------------------------------------------------------------------------------------
def quat2mat(q_wxyz):
    w, x, y, z = q_wxyz
    n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
    w, x, y, z = w / n, x / n, y / n, z / n
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w),     2 * (x * z + y * w)],
        [2 * (x * y + z * w),     1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w),     2 * (y * z + x * w),     1 - 2 * (x * x + y * y)],
    ]


def matvec(M, v):
    return [M[r][0] * v[0] + M[r][1] * v[1] + M[r][2] * v[2] for r in range(3)]


def parse_axis_map(spec):
    """'x,-z,y' -> 3x3 sign/permutation matrix S with world_i = +/- motive_axis."""
    axes = {"x": 0, "y": 1, "z": 2}
    S = [[0.0] * 3 for _ in range(3)]
    toks = [t.strip().lower() for t in spec.split(",")]
    if len(toks) != 3:
        raise SystemExit(f"AXIS_MAP needs 3 comma tokens, got {spec!r}")
    for r, tok in enumerate(toks):
        sign = -1.0 if tok[:1] == "-" else 1.0
        tok = tok.lstrip("+-")
        if tok not in axes:
            raise SystemExit(f"AXIS_MAP token {tok!r} not one of x/y/z")
        S[r][axes[tok]] = sign
    det = (S[0][0] * (S[1][1] * S[2][2] - S[1][2] * S[2][1])
           - S[0][1] * (S[1][0] * S[2][2] - S[1][2] * S[2][0])
           + S[0][2] * (S[1][0] * S[2][1] - S[1][1] * S[2][0]))
    if abs(det - 1.0) > 1e-6:
        raise SystemExit(f"AXIS_MAP {spec!r} is not a right-handed rotation (det={det:+.0f}); fix a sign")
    return S


def site_world(pos_m, quat_wxyz, offset_body, S):
    """world IMU-site = S @ (pos_motive + R_motive @ IMU_OFFSET_body)."""
    R = quat2mat(quat_wxyz)
    site_m = [pos_m[i] + (R[i][0] * offset_body[0] + R[i][1] * offset_body[1] + R[i][2] * offset_body[2])
              for i in range(3)]
    return matvec(S, site_m)


class VelocityFD:
    """Finite-difference velocity with a one-pole low-pass (jitter-robust)."""
    def __init__(self, tau_s):
        self.tau = tau_s
        self.prev_p = None
        self.prev_t = None
        self.v = [0.0, 0.0, 0.0]

    def update(self, p, t):
        if self.prev_p is None:
            self.prev_p, self.prev_t = p, t
            return self.v
        dt = t - self.prev_t
        if dt > 1e-6:
            a = dt / (self.tau + dt)
            for k in range(3):
                self.v[k] += a * ((p[k] - self.prev_p[k]) / dt - self.v[k])
            self.prev_p, self.prev_t = p, t
        return self.v


# ------------------------------------------------------------------------------------------
#  Main
# ------------------------------------------------------------------------------------------
def _auto_iface_ip(robot_subnet="192.168.123."):
    """Return this machine's IP on the robot subnet (cross-platform), or None. Uses a UDP
    'connect' (sends no packets) so the OS reports which local NIC would route to the robot net."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect((robot_subnet + "1", 9))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip if ip.startswith(robot_subnet) else None
    except Exception:
        return None


def main():
    cfg = CONFIG
    S = parse_axis_map(cfg["AXIS_MAP"])
    offset = tuple(float(x) for x in cfg["IMU_OFFSET_M"])
    rate = max(1.0, float(cfg["RATE_HZ"]))
    period = max(1, int(rate))
    dt = 1.0 / rate

    # Raise the Windows timer resolution so the pacer can approach RATE_HZ (default ~15 ms).
    if sys.platform == "win32":
        try:
            ctypes.windll.winmm.timeBeginPeriod(1)
        except Exception:
            pass

    # DDS imported here so a missing dependency gives a clear message (not an import crash).
    try:
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher
        from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_
        from unitree_sdk2py.idl.default import unitree_go_msg_dds__SportModeState_
    except Exception as e:
        sys.exit(f"[publisher] cannot import unitree_sdk2py ({e}).\n"
                 f"             Install from source: clone unitree_sdk2_python, then  pip install -e .\n"
                 f"             (needs the cyclonedds bindings + native CycloneDDS on Windows).")

    print(f"[publisher] loading Motive from {cfg['MOTIVE_DIR']} ...", flush=True)
    mot = Motive(cfg["MOTIVE_DIR"])            # loads the DLL only; does NOT take the cameras yet
    # From TT_Initialize onward the cameras are owned -> everything is inside try/finally so a
    # failure (bad cal path, missing rigid body, DDS error) ALWAYS releases them. Otherwise the
    # next run fails with the camera-mutex error until reboot.
    try:
        print(f"[publisher] DLL build {mot.build_number()}; initializing (Motive GUI must be CLOSED) ...", flush=True)
        mot.initialize()
        print(f"[publisher] cameras online: {mot.camera_count()}", flush=True)

        # Load the rigid-body source FIRST (profile), then the calibration LAST, so the .cal you
        # name in CONFIG always wins even if the profile happens to bundle its own calibration.
        if cfg["PROFILE"]:
            mot.load_profile(cfg["PROFILE"])
            print(f"[publisher] profile loaded: {os.path.basename(cfg['PROFILE'])}", flush=True)
        if not cfg["CALIBRATION"]:
            sys.exit("[publisher] CALIBRATION path is empty -- set it in the CONFIG block.")
        mot.load_calibration(cfg["CALIBRATION"])
        print(f"[publisher] calibration loaded: {os.path.basename(cfg['CALIBRATION'])}", flush=True)

        idx = mot.rigid_body_index(cfg["RIGID_BODY"])
        if idx < 0:
            names = [mot.rigid_body_name(i) for i in range(mot.rigid_body_count())]
            sys.exit(f"[publisher] rigid body '{cfg['RIGID_BODY']}' not found.\n"
                     f"             Available: {names}\n"
                     f"             Set PROFILE to a .motive that contains it, or create it in the Motive GUI.")
        print(f"[publisher] tracking rigid body '{cfg['RIGID_BODY']}' (index {idx})", flush=True)

        # --- DDS publisher ---
        iface = cfg["DDS_INTERFACE"].strip()
        if not iface:
            detected = _auto_iface_ip()
            if detected:
                iface = detected
                print(f"[publisher] auto-detected robot-subnet IP: {iface}", flush=True)
            else:
                print("[publisher] WARNING: no 192.168.123.x route on this machine -- DDS may not reach "
                      "the robot. Connect to the robot (wired, or its WiFi) so this PC gets a "
                      "192.168.123.x address.", flush=True)
        # Bind the chosen interface. Passing an IP works on Linux, but Windows CycloneDDS often
        # rejects it ("<ip>: does not match an available interface") -- so fall back to
        # auto-determine, which lets CycloneDDS pick the NIC itself (it prefers a real subnet like
        # the robot's 192.168.123.x over the link-local 169.254.x camera net). A failed bind does
        # NOT create the domain, so the retry is safe in-process.
        bound = False
        if iface:
            try:
                ChannelFactoryInitialize(cfg["DDS_DOMAIN"], iface)
                print(f"[publisher] DDS domain {cfg['DDS_DOMAIN']} on interface '{iface}'", flush=True)
                bound = True
            except Exception as e:
                print(f"[publisher] could not bind interface '{iface}' ({e}); "
                      "falling back to auto-determine.", flush=True)
        if not bound:
            ChannelFactoryInitialize(cfg["DDS_DOMAIN"])
            print(f"[publisher] DDS domain {cfg['DDS_DOMAIN']} (auto-determine -- CycloneDDS picks the NIC)",
                  flush=True)
        pub = ChannelPublisher(cfg["OUT_TOPIC"], SportModeState_)
        pub.Init()
        msg = unitree_go_msg_dds__SportModeState_()

        # Optional unicast UDP sink: pose ALSO goes here, which crosses WiFi where DDS multicast
        # can't. A pose_udp_bridge.py on the wired-robot laptop turns it back into DDS.
        import socket as _socket, struct as _struct
        udp_sock = udp_addr = None
        if cfg["UDP_SINK"].strip():
            _host, _, _port = cfg["UDP_SINK"].strip().rpartition(":")
            udp_addr = (_host, int(_port))
            udp_sock = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
            print(f"[publisher] ALSO sending pose by unicast UDP -> {_host}:{_port}", flush=True)

        fd = VelocityFD(cfg["VEL_LOWPASS_MS"] * 1e-3)
        # Outlier gate state: a single bad rigid-body solve pops the pose for one frame -> a
        # phantom 1-5 m/s velocity spike when differenced. Reject + hold the last good pose.
        gate_speed = float(cfg.get("OUTLIER_MAX_SPEED", 0.0))
        gate_err   = float(cfg.get("OUTLIER_MAX_ERR_MM", 0.0))
        gate_hold  = int(cfg.get("OUTLIER_HOLD_MAX", 5))
        last_p, last_t, last_v = None, None, [0.0, 0.0, 0.0]
        n_reject_run = n_reject_total = 0
        if gate_speed > 0 or gate_err > 0:
            print(f"[publisher] OUTLIER GATE on: reject if speed>{gate_speed:.1f}m/s"
                  + (f" or err>{gate_err:.1f}mm" if gate_err > 0 else "")
                  + f" -> hold last good (<= {gate_hold} in a row, then accept as real motion)", flush=True)

        def _emit(pos, vel):                       # publish one (pos, vel) sample to DDS (+ UDP sink)
            for k in range(3):
                msg.position[k] = float(pos[k]); msg.velocity[k] = float(vel[k])
            pub.Write(msg)
            if udp_sock is not None:
                udp_sock.sendto(b"MCAP" + _struct.pack("<7d", now, pos[0], pos[1], pos[2],
                                                        vel[0], vel[1], vel[2]), udp_addr)

        print(f"[publisher] PUBLISHING '{cfg['OUT_TOPIC']}' @ {rate:.0f} Hz  (Ctrl+C to stop)\n", flush=True)

        n, n_untracked, t0, next_t = 0, 0, time.time(), time.time()
        while True:
            now = time.time()
            if now < next_t:
                time.sleep(min(dt, next_t - now))
                continue
            next_t += dt
            try:
                mot.update()                       # process the latest camera frame
                if not mot.is_tracked(idx):
                    n_untracked += 1
                    if n_untracked % period == 1:
                        print("[publisher] rigid body NOT tracked (occluded?) -- holding, not publishing", flush=True)
                    continue
                if n_untracked:                    # tracking just resumed
                    n_untracked = 0
                    fd.prev_p = None               # reset FD so the first post-gap sample isn't a jump
                    last_p = None                  # don't gate the re-acquired pose against a stale sample
                pos_m, quat = mot.location(idx)
                site = site_world(pos_m, quat, offset, S)

                # --- outlier gate: drop glitch frames so a bad solve can't inject a phantom spike ---
                reject, reason = False, ""
                if gate_err > 0.0:
                    err_mm = mot.mean_error_mm(idx)
                    if err_mm > gate_err:
                        reject, reason = True, f"err {err_mm:.1f}>{gate_err:.1f}mm"
                if not reject and gate_speed > 0.0 and last_p is not None:
                    d = math.sqrt(sum((site[k] - last_p[k]) ** 2 for k in range(3)))
                    gap = now - last_t
                    if gap > 1e-6 and d / gap > gate_speed:
                        reject, reason = True, f"jump {d*100:.1f}cm/{gap*1e3:.0f}ms={d/gap:.1f}m/s"
                if reject and n_reject_run < gate_hold:
                    n_reject_run += 1; n_reject_total += 1
                    if last_p is not None:         # hold last good pose -> no phantom spike downstream
                        _emit(last_p, last_v)
                    if n_reject_total % period == 1:
                        print(f"[publisher] OUTLIER rejected ({reason}) -> holding ({n_reject_total} total)", flush=True)
                    continue
                if reject:                         # gate_hold in a row -> sustained = real motion, accept + reset FD
                    fd.prev_p = None
                    print(f"[publisher] outlier persisted {gate_hold} frames -> accepting as real motion (FD reset)", flush=True)
                n_reject_run = 0
                # ------------------------------------------------------------------------------------

                v = fd.update(site, now)
                _emit(site, v)
                last_p, last_t, last_v = list(site), now, list(v)
                n += 1
                if n % period == 0:
                    print(f"[publisher] {now - t0:6.1f}s  pos=[{site[0]:+.3f},{site[1]:+.3f},{site[2]:+.3f}]"
                          f"  vel=[{v[0]:+.3f},{v[1]:+.3f},{v[2]:+.3f}]  err={mot.mean_error_mm(idx):.2f}mm"
                          + (f"  rej={n_reject_total}" if n_reject_total else ""), flush=True)
            except Exception as e:                 # one transient Motive/DDS hiccup shouldn't kill the feed
                print(f"[publisher] transient error: {e} -- continuing", flush=True)
                time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n[publisher] stopping ...", flush=True)
    finally:
        mot.shutdown()
        print("[publisher] cameras released. bye.", flush=True)


if __name__ == "__main__":
    main()
