# answers_from_main.md — replies to the OptiTrack agent's questions

Answers are pulled from project source (`dds_tools/base_estimator_node.py`,
`mujoco_mpc/mujoco_mpc/mjpc/deploy/h12_control_node.cc`) and the project record. Where something
is **our decision to make** vs **not yet validated on hardware**, it's flagged honestly — don't
read "recommended" as "tested".

---

## Q1. Exact rigid body name for the H1-2 base/pelvis

**Free choice — it does NOT affect the DDS side.** The DDS topic is always `rt/sportmodestate`;
the rigid-body name only matters as the **VRPN tracker name** your client subscribes to. Pick one,
use it consistently, and tell us what you picked.

- **Recommended name: `h1_2_pelvis`** (the model's floating base link is the *pelvis*).
- The bridge will then subscribe `vrpn.receiver.Tracker("h1_2_pelvis@tcp://<MoCapIP>:3883")`.
- ⚠️ Don't reuse or delete other people's saved rigid bodies in the Assets pane.

---

## Q2. Frame transform details (axis swaps / sign flips / IMU_OFFSET) — ★ the important one

### 2a. Up-axis / handedness (the classic mocap gotcha)
- **Motive defaults to Y-up (right-handed).** Our world (MuJoCo) is **Z-up (right-handed),
  floor at z = 0, +x = robot forward.**
- **Preferred fix:** in Motive's **Data Streaming** pane set **Up Axis = Z** (Motive can stream
  Z-up for both NatNet and VRPN in current versions — verify it's there for your version). Then,
  with the ground plane/origin set so the floor is z=0 and +x points where the robot faces, you
  can publish position **directly, no swap**.
- **If you must stream Y-up:** convert in the bridge. The standard Y-up(RH) → Z-up(RH) map is a
  −90° rotation about X: `x_world = x_m`, `y_world = -z_m`, `z_world = y_m`. **BUT the exact
  signs/swap depend on how you orient the ground plane/origin**, so do **not** trust the formula —
  confirm it with the motion test in Q6 (move +1 m forward ⇒ `x` increases by 1; lift 0.5 m ⇒ `z`
  increases by 0.5). Lock the mapping empirically.

### 2b. IMU_OFFSET (pelvis → IMU site), confirmed value
```
IMU_OFFSET = [-0.04452, -0.01891, 0.27756]   # meters, in the PELVIS body frame
```
(Identical in `base_estimator_node.py:51` and `h12_control_node.cc:317`.)

### 2c. What point you must publish, and the math
We publish the **IMU-site world pose**, not the pelvis origin. The node recovers the pelvis with
the **IMU quaternion** (from `rt/lowstate`):

- **Node (consumer), `h12_control_node.cc:759-767`:**
  `roff = R(imu_quat) · IMU_OFFSET` ; `pelvis_pos = site_p − roff` ; `pelvis_v = site_v − (ω_world × roff)`
- **Estimator (the thing you replace), `base_estimator_node.py:375-382`:**
  `roff = R · IMU_OFFSET` ; `site_p = [x, y, height] + roff` ; `site_v = v + ω_world × roff`

So the node will subtract `R·IMU_OFFSET` (using the live IMU orientation) from whatever you put in
`position`. Two clean ways to satisfy that:

1. **★ Easiest & most robust — track the IMU site directly.** Set the Motive rigid-body **pivot at
   the physical pelvis IMU location**, axes aligned to the pelvis. Then the streamed position *is*
   the IMU-site world position → publish it directly, **no offset math, no R needed in the bridge**.
   The node's IMU-quat subtraction then recovers the pelvis correctly. **This is what we recommend.**
2. **Track the pelvis origin and add the offset.** If your pivot is at the pelvis frame origin,
   publish `site_p = pelvis_world + R(imu_quat)·IMU_OFFSET` — which means subscribing `rt/lowstate`
   for the quaternion and rotating IMU_OFFSET. More moving parts; only do this if option 1 isn't
   feasible.

**Why it matters for us specifically:** the vertical component (0.278 m) sets the height mapping,
and the lever rotates with tilt — and our task is *leaning*, so tilt accuracy matters. Getting the
tracked point right (option 1) avoids a tilt-dependent base error.

---

## Q3. VRPN vs NatNet for Motive 2.2 + working client settings

- **Not yet finalized on our hardware** (you're standing the system up now — we have not run
  OptiTrack end-to-end). **Recommendation for Motive 2.2: use VRPN.** The lab PDF explicitly flags
  the NatNet Python client (`ratcave/natnetclient`) as **broken on Ubuntu 20.04 / Python 3.8 /
  Motive 2.2**. VRPN avoids that.
- **Motive side:** Data Streaming → Transmission Type = **Unicast**, **Broadcast VRPN = On**.
- **Client (pyvrpn), from the PDF's working example:**
  ```python
  import vrpn
  t = vrpn.receiver.Tracker("h1_2_pelvis@tcp://192.168.50.10:3883")  # use YOUR system IP
  t.register_change_handler("h1_2_pelvis", callback, "position")
  while True:
      t.mainloop()   # pumps; callback receives {'position': (x,y,z), 'quaternion': (...)}
  ```
- If your Motive is **newer than 2.2**, NatNet becomes viable (`NatNetSDK`/`NatNetClient`); but
  default to VRPN unless you confirm NatNet works on the client OS.

---

## Q4. Known-good `rt/sportmodestate` field mapping

**Populate only these two arrays; leave everything else default/zero.** This is the exact mapping
the estimator publishes and the node reads (validated on the twin to truth-parity):

| Field | Value | Source |
|---|---|---|
| `msg.position[0:3]` | base **IMU-site world position** (x, y, z) meters | `base_estimator_node.py:381`, node reads `:619` |
| `msg.velocity[0:3]` | base **IMU-site world velocity** (vx, vy, vz) m/s | `base_estimator_node.py:382`, node reads `:620` |
| everything else | leave at constructor default | not read |

- Message type: `unitree_go::msg::dds_::SportModeState_`
  (Python: `from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_`,
  construct `unitree_go_msg_dds__SportModeState_()`).
- **★ Velocity is optional in the default config:** the node **re-derives base linear velocity
  from `LPF(d/dt position)`** (the `vel_lpf_ms` path, on by default — `h12_control_node.cc:925`),
  so it does **not** use your `velocity` field for the base linvel unless that's turned off. ⇒
  **Publish accurate, low-jitter `position`; you may finite-difference `velocity` or leave it
  zero.** Clean position beats clever velocity.
- **Orientation is NOT in your scope** — base orientation comes from the IMU (`rt/lowstate`,
  `qpos[3:7]`), not from `sportmodestate`.

---

## Q5. Known-good network config

**No DNS — all static IPs. Two separate networks; the bridge straddles both.**

| Item | Value |
|---|---|
| **Motive / streaming IP** | bigger MoCap `192.168.50.10` **or** smaller `192.168.50.24` — *confirm which you used* |
| **MoCap network** | WiFi **`IRLab`**, subnet `192.168.50.x` |
| **Robot DDS subnet** | `192.168.123.x` (robot/pc4 ≈ `.164`; laptop `.4` via DHCP, or set `.99/24`) |
| **Robot DDS NIC (laptop)** | USB-Ethernet dongle, name like `enx00e04c681314` — **read live** with `ip -br link` |
| **DDS domain ID** | **0** (real robot). NOT 1 (that's sim — don't use docker/dds_master scripts) |
| **VRPN** | TCP **unicast**, port **3883** |
| **NatNet** | UDP **multicast** `239.255.42.99`, data port `1511`, comm port `1510` |
| **DDS discovery** | CycloneDDS domain-0 multicast on the **pinned `enx` NIC** |

**Firewall / gotchas:**
- **Windows Firewall on the Motive PC** may block streaming — allow Motive through (inbound TCP
  **3883** for VRPN; UDP **1510/1511** + multicast for NatNet).
- **★ Tailscale MUST be OFF on the bridge/laptop** (`sudo tailscale down`). If any DDS process runs
  with auto-interface while `tailscale0` is up, CycloneDDS advertises the `100.x` address into
  domain 0 and **breaks discovery with the robot**. Then **pin DDS to the `enx` NIC** so it only
  advertises the wired locator.
- The bridge machine must reach **both** `192.168.50.x` (MoCap, over WiFi) **and** `192.168.123.x`
  (robot, over `enx`) at once. The laptop already has both — DDS pinned to `enx`, MoCap over WiFi.

---

## Q6. Reference test / success criteria

We have **not** validated OptiTrack itself yet, but here is the criteria set (from how we validate
the equivalent estimator path). Declare success when all pass:

1. **Topic is alive:** run in the `h1_mujoco` venv:
   `python dds_tools/dds_topic_check.py --extra rt/sportmodestate`
   → expect `rt/sportmodestate ARRIVING ✅`, rate **≈ your publish Hz (target 200, ≥ planner
   ~50–65 Hz)**, **finite** (no NaN), decoded position printed.
2. **Static test:** hold the body still → `velocity ≈ 0` (< ~0.02 m/s), `position` constant.
3. **★ Frame/axis validator (motion test):** move the tracked point a known distance/direction:
   - slide **+1 m forward** ⇒ `position.x` increases by ~1.0 (and only x)
   - slide **+1 m left** ⇒ the correct lateral axis moves with the correct sign
   - **lift +0.5 m** ⇒ `position.z` increases by ~0.5
   This is what locks down the up-axis and any sign flips. Don't skip it.
4. **Height sanity:** with the robot standing, the published **IMU-site z ≈ 1.3 m** (the IMU sits
   ~0.28 m above the pelvis origin); after the node backs out IMU_OFFSET, the **recovered pelvis
   z ≈ 1.03 m** (our home-keyframe base height). Tape-measure the tracked point's true height and
   confirm the published z matches it.
5. **Accuracy thresholds (planner sensitivity):** the controller mis-balances around **~0.3 m/s
   velocity / ~10 cm position** error. OptiTrack should be **sub-cm** position (it does mm) — far
   inside margin.
6. **(Use-case B) vs the software estimator:** if you record OptiTrack alongside
   `base_estimator_node.py`, the estimator's twin-validated reference was **RMS ≈ 0.016 m/s, drift
   ≈ 7 mm / 25 s** — OptiTrack should be smoother and drift-free (it's the ground truth).

---

## Starter bridge skeleton (pyvrpn → DDS) — UNTESTED, a starting point

Drop-in sibling to `base_estimator_node.py`; publishes the SAME topic/message. Marked TODOs are
the parts you must pin down empirically (frame transform) or by placement (IMU site).

```python
#!/usr/bin/env python3
"""OptiTrack (VRPN) -> rt/sportmodestate bridge. Replaces base_estimator_node.py with ground truth.
Run on the laptop (reaches MoCap over WiFi + robot over enx). Tailscale OFF; DDS pinned to enx."""
import argparse, time
import numpy as np
import vrpn  # pyvrpn

def to_world(p_motive):
    # TODO VERIFY WITH THE MOTION TEST (Q6.3). If Motive streams Z-up + origin aligned: return p.
    # If Motive streams Y-up (RH): x,y,z = p[0], -p[2], p[1]   (then re-check signs!)
    return np.asarray(p_motive, dtype=float)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", default="h1_2_pelvis")          # VRPN tracker name (Q1)
    ap.add_argument("--mocap-ip", default="192.168.50.10")    # bigger MoCap (Q5)
    ap.add_argument("--port", type=int, default=3883)
    ap.add_argument("--iface", default=None, help="robot DDS NIC, e.g. enx... (read via 'ip -br link')")
    ap.add_argument("--domain", type=int, default=0)
    ap.add_argument("--rate", type=float, default=200.0)
    ap.add_argument("--out-topic", default="rt/sportmodestate")  # use rt/sportmodestate_est for offline compare
    a = ap.parse_args()

    from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
    from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_
    from unitree_sdk2py.idl.default import unitree_go_msg_dds__SportModeState_
    if a.iface:
        ChannelFactoryInitialize(a.domain, a.iface)   # pin the wired NIC (Tailscale must be down)
    else:
        ChannelFactoryInitialize(a.domain)            # autodetermine — pin --iface for the real robot!

    state = {"p": None, "t": None, "v": np.zeros(3)}
    def cb(userdata, data):
        p = to_world(data["position"])                # 3-vec; data also has "quaternion"
        now = time.monotonic()
        if state["p"] is not None and state["t"] is not None:
            dt = max(now - state["t"], 1e-3)
            state["v"] = (p - state["p"]) / dt         # optional; node re-derives velocity anyway
        state["p"], state["t"] = p, now

    trk = vrpn.receiver.Tracker(f"{a.body}@tcp://{a.mocap_ip}:{a.port}")
    trk.register_change_handler(a.body, cb, "position")

    pub = ChannelPublisher(a.out_topic, SportModeState_); pub.Init()
    msg = unitree_go_msg_dds__SportModeState_()
    period = 1.0 / a.rate
    print(f"[bridge] {a.body}@{a.mocap_ip}:{a.port} -> {a.out_topic} @ {a.rate:.0f}Hz (domain {a.domain})")
    while True:
        trk.mainloop()                                 # pump VRPN
        if state["p"] is not None:
            # IMPORTANT: state['p'] must be the IMU-SITE world pose. Track the IMU site (Q2c option 1),
            # OR add R(imu_quat)@IMU_OFFSET here (option 2, IMU_OFFSET=[-0.04452,-0.01891,0.27756]).
            for k in range(3):
                msg.position[k] = float(state["p"][k])
                msg.velocity[k] = float(state["v"][k])
            pub.Write(msg)
        time.sleep(period)

if __name__ == "__main__":
    main()
```

**Verify after wiring:** `python dds_tools/dds_topic_check.py --extra rt/sportmodestate` →
ARRIVING ✅ at your rate, finite, position tracks the motion test (Q6).

---

### If you still need something from us
Append to `questions_for_main.md`. Most likely follow-ups we can answer fast: the exact pelvis IMU
physical location for marker placement, the home-keyframe base pose, or whether to flip the
node's `vel_lpf_ms` off so it uses your published velocity directly.
