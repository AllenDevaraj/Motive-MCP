"""Dump the calibrated camera positions / orientations from Motive (headless, ctypes).

Run ON the Motive PC with the Motive GUI CLOSED (the API owns the cameras):

    .\.venv\Scripts\python.exe dump_cameras.py  [> cameras.json]

Reuses the loader + CONFIG (MOTIVE_DIR, CALIBRATION) of publish_sportmodestate.py.
Prints one line per camera: serial, position (m, Motive frame, y-up), 3x3 orientation.
"""
import ctypes as c
import json
import sys

import publish_sportmodestate as P


def main():
    cfg = P.CONFIG
    m = P.Motive(cfg["MOTIVE_DIR"])
    L = m.lib
    L.TT_CameraSerial.restype = c.c_int
    L.TT_CameraSerial.argtypes = [c.c_int]
    L.TT_CameraName.restype = c.c_char_p
    L.TT_CameraName.argtypes = [c.c_int]
    for fn in ("TT_CameraXLocation", "TT_CameraYLocation", "TT_CameraZLocation"):
        f = getattr(L, fn)
        f.restype = c.c_float
        f.argtypes = [c.c_int]
    L.TT_CameraOrientationMatrix.restype = c.c_float
    L.TT_CameraOrientationMatrix.argtypes = [c.c_int, c.c_int]

    out = []
    try:
        m.initialize()
        if cfg.get("CALIBRATION"):
            m.load_calibration(cfg["CALIBRATION"])
        m.update()
        for i in range(m.camera_count()):
            name = L.TT_CameraName(i)
            out.append({
                "index": i,
                "serial": int(L.TT_CameraSerial(i)),
                "name": name.decode(errors="replace") if name else "",
                "pos_m": [float(L.TT_CameraXLocation(i)),
                          float(L.TT_CameraYLocation(i)),
                          float(L.TT_CameraZLocation(i))],
                "R": [[float(L.TT_CameraOrientationMatrix(i, r * 3 + k)) for k in range(3)]
                      for r in range(3)],
            })
    finally:
        m.shutdown()
    json.dump({"frame": "Motive (y-up unless Up Axis changed)", "cameras": out},
              sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
