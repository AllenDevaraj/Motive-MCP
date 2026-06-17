"""ctypes binding to the OptiTrack Motive 2.2 NPTrackingTools API (NPTrackingToolsx64.dll).

Runs ON THE WINDOWS MOTIVE PC. Loads the 64-bit DLL directly via ctypes — no C++ compiler
needed. The API surface below was taken verbatim from the on-disk header on this exact install:
    C:\\Program Files\\OptiTrack\\Motive\\inc\\NPTrackingTools.h   (Motive 2.2.0.1, build 2019-11-08)

IMPORTANT: this module is UNTESTED on the dev machine it was written on (Linux, no DLL/cameras).
Validate on the Windows PC with:  python motive_mcp_server.py --selftest

Calling TT_Initialize() takes ownership of the camera system, so the Motive GUI must be CLOSED
while this runs (TT_TestSoftwareMutex / TT_Initialize will fail otherwise).
"""
from __future__ import annotations

import ctypes
import os

DEFAULT_MOTIVE_DIR = r"C:\Program Files\OptiTrack\Motive"
NPRESULT_SUCCESS = 0


class MotiveError(RuntimeError):
    """Raised when an NPTrackingTools call returns a non-success NPRESULT."""


class MotiveAPI:
    def __init__(self, motive_dir: str = DEFAULT_MOTIVE_DIR, dll_path: str | None = None):
        self.motive_dir = motive_dir
        self.dll_path = dll_path or os.path.join(motive_dir, "lib", "NPTrackingToolsx64.dll")
        if not os.path.isfile(self.dll_path):
            raise MotiveError(f"NPTrackingToolsx64.dll not found at {self.dll_path}")
        # Dependent DLLs live alongside the main DLL; add them to the loader search path.
        for d in (motive_dir, os.path.join(motive_dir, "lib")):
            if os.path.isdir(d):
                try:
                    os.add_dll_directory(d)  # Python 3.8+
                except (AttributeError, OSError):
                    pass
        os.environ["PATH"] = motive_dir + os.pathsep + os.environ.get("PATH", "")
        self.lib = ctypes.CDLL(self.dll_path)
        self._declare()

    # --- signature declarations (from NPTrackingTools.h) ------------------------------------
    def _declare(self) -> None:
        L, c = self.lib, ctypes
        # lifecycle
        for fn in ("TT_Initialize", "TT_Shutdown", "TT_TestSoftwareMutex",
                   "TT_Update", "TT_UpdateSingleFrame", "TT_BuildNumber"):
            getattr(L, fn).restype = c.c_int
        L.TT_GetResultString.restype = c.c_char_p
        L.TT_GetResultString.argtypes = [c.c_int]
        # profiles / calibration / rigid-body files (char* path -> NPRESULT)
        for fn in ("TT_LoadProfile", "TT_SaveProfile", "TT_LoadCalibration",
                   "TT_LoadRigidBodies", "TT_AddRigidBodies", "TT_SaveRigidBodies"):
            f = getattr(L, fn)
            f.restype = c.c_int
            f.argtypes = [c.c_char_p]
        # streaming
        L.TT_StreamVRPN.restype = c.c_int
        L.TT_StreamVRPN.argtypes = [c.c_bool, c.c_int]
        L.TT_StreamNP.restype = c.c_int
        L.TT_StreamNP.argtypes = [c.c_bool]
        # cameras
        L.TT_CameraCount.restype = c.c_int
        L.TT_CameraName.restype = c.c_char_p
        L.TT_CameraName.argtypes = [c.c_int]
        L.TT_SetCameraFrameRate.restype = c.c_bool
        L.TT_SetCameraFrameRate.argtypes = [c.c_int, c.c_int]
        L.TT_CameraFrameRate.restype = c.c_int
        L.TT_CameraFrameRate.argtypes = [c.c_int]
        # rigid bodies
        L.TT_RigidBodyCount.restype = c.c_int
        L.TT_RigidBodyName.restype = c.c_char_p
        L.TT_RigidBodyName.argtypes = [c.c_int]
        L.TT_IsRigidBodyTracked.restype = c.c_bool
        L.TT_IsRigidBodyTracked.argtypes = [c.c_int]
        L.TT_RigidBodyEnabled.restype = c.c_bool
        L.TT_RigidBodyEnabled.argtypes = [c.c_int]
        L.TT_SetRigidBodyEnabled.argtypes = [c.c_int, c.c_bool]
        L.TT_RigidBodyMeanError.restype = c.c_float
        L.TT_RigidBodyMeanError.argtypes = [c.c_int]
        L.TT_RemoveRigidBody.restype = c.c_int
        L.TT_RemoveRigidBody.argtypes = [c.c_int]
        L.TT_ClearRigidBodyList.argtypes = []
        L.TT_CreateRigidBody.restype = c.c_int
        L.TT_CreateRigidBody.argtypes = [c.c_char_p, c.c_int, c.c_int, c.POINTER(c.c_float)]
        # void TT_RigidBodyLocation(int, float* x,y,z, qx,qy,qz,qw, yaw,pitch,roll)
        L.TT_RigidBodyLocation.argtypes = [c.c_int] + [c.POINTER(c.c_float)] * 10

    # --- helpers ----------------------------------------------------------------------------
    def _check(self, code: int, what: str) -> None:
        if code != NPRESULT_SUCCESS:
            raw = self.lib.TT_GetResultString(code)
            msg = raw.decode(errors="replace") if raw else f"NPRESULT {code}"
            raise MotiveError(f"{what} failed: {msg} (code {code})")

    # --- lifecycle --------------------------------------------------------------------------
    def initialize(self) -> None:
        self._check(self.lib.TT_Initialize(), "TT_Initialize")

    def shutdown(self) -> None:
        self.lib.TT_Shutdown()

    def update(self) -> int:
        return self.lib.TT_Update()

    def build_number(self) -> int:
        return int(self.lib.TT_BuildNumber())

    # --- files ------------------------------------------------------------------------------
    def load_profile(self, path: str) -> None:
        self._check(self.lib.TT_LoadProfile(path.encode()), f"TT_LoadProfile({path})")

    def load_calibration(self, path: str) -> None:
        self._check(self.lib.TT_LoadCalibration(path.encode()), f"TT_LoadCalibration({path})")

    def load_rigid_bodies(self, path: str) -> None:
        self._check(self.lib.TT_LoadRigidBodies(path.encode()), f"TT_LoadRigidBodies({path})")

    def add_rigid_bodies(self, path: str) -> None:
        self._check(self.lib.TT_AddRigidBodies(path.encode()), f"TT_AddRigidBodies({path})")

    def save_rigid_bodies(self, path: str) -> None:
        self._check(self.lib.TT_SaveRigidBodies(path.encode()), f"TT_SaveRigidBodies({path})")

    # --- streaming --------------------------------------------------------------------------
    def stream_vrpn(self, enabled: bool, port: int = 3883) -> None:
        self._check(self.lib.TT_StreamVRPN(bool(enabled), int(port)), "TT_StreamVRPN")

    def stream_natnet(self, enabled: bool) -> None:
        self._check(self.lib.TT_StreamNP(bool(enabled)), "TT_StreamNP")

    # --- cameras ----------------------------------------------------------------------------
    def camera_count(self) -> int:
        return int(self.lib.TT_CameraCount())

    def camera_name(self, i: int) -> str:
        n = self.lib.TT_CameraName(i)
        return n.decode(errors="replace") if n else f"camera{i}"

    def camera_frame_rate(self, i: int) -> int:
        return int(self.lib.TT_CameraFrameRate(i))

    def set_frame_rate(self, hz: int) -> bool:
        ok = True
        for i in range(self.camera_count()):
            ok = bool(self.lib.TT_SetCameraFrameRate(i, int(hz))) and ok
        return ok

    # --- rigid bodies -----------------------------------------------------------------------
    def rigid_body_count(self) -> int:
        return int(self.lib.TT_RigidBodyCount())

    def rigid_body_name(self, i: int) -> str:
        n = self.lib.TT_RigidBodyName(i)
        return n.decode(errors="replace") if n else f"rb{i}"

    def rigid_body_index(self, name: str) -> int:
        for i in range(self.rigid_body_count()):
            if self.rigid_body_name(i) == name:
                return i
        return -1

    def is_tracked(self, i: int) -> bool:
        return bool(self.lib.TT_IsRigidBodyTracked(i))

    def is_enabled(self, i: int) -> bool:
        return bool(self.lib.TT_RigidBodyEnabled(i))

    def set_enabled(self, i: int, enabled: bool) -> None:
        self.lib.TT_SetRigidBodyEnabled(i, bool(enabled))

    def mean_error(self, i: int) -> float:
        return float(self.lib.TT_RigidBodyMeanError(i))

    def remove_rigid_body(self, i: int) -> None:
        self._check(self.lib.TT_RemoveRigidBody(i), "TT_RemoveRigidBody")

    def create_rigid_body(self, name: str, rb_id: int, marker_xyz: list[float]) -> None:
        """marker_xyz: flat [x,y,z, x,y,z, ...] in METERS, relative to the desired pivot."""
        if len(marker_xyz) % 3 != 0:
            raise MotiveError("marker_xyz length must be a multiple of 3")
        n = len(marker_xyz) // 3
        arr = (ctypes.c_float * len(marker_xyz))(*[float(v) for v in marker_xyz])
        self._check(self.lib.TT_CreateRigidBody(name.encode(), int(rb_id), n, arr),
                    f"TT_CreateRigidBody({name})")

    def rigid_body_location(self, i: int) -> dict:
        vals = [ctypes.c_float(0.0) for _ in range(10)]
        self.lib.TT_RigidBodyLocation(i, *[ctypes.byref(v) for v in vals])
        x, y, z, qx, qy, qz, qw, yaw, pitch, roll = (v.value for v in vals)
        return {"x": x, "y": y, "z": z,
                "qx": qx, "qy": qy, "qz": qz, "qw": qw,
                "yaw": yaw, "pitch": pitch, "roll": roll}
