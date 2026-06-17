# OptiTrack ↔ H1-2 / MJPC — Integration Handoff

**Audience:** a fresh agent (and operator) setting up the lab's **OptiTrack** motion-capture
system to feed our humanoid controller. You have **zero prior context** on this project — this
document gives you all of it.

**Companion file:** `Getting started with OptiTrack.pdf` (the lab's Motive how-to). This `.md`
is the **why + our-side integration spec**; the PDF is the **Motive-side button-by-button**.
Read this first, then the PDF.

**You do NOT need to understand the controller internals.** Your job is to produce one thing:
a clean stream of the robot's **base position** in a world frame, delivered onto a specific DDS
topic. Everything below explains what that means and why.

**How to ask the main agent (me) questions:** if you need something only the main project
context can answer (a frame convention, an offset value, existing bridge code, a file's
contents), write a file named **`questions_for_main.md`** with numbered, specific questions.
The operator will carry it back to me and return my answers in **`answers_from_main.md`**.
Keep questions concrete (paths, values, names) — see §10 for the high-value ones to ask up front.

---

## 0. TL;DR — the one job

The robot can't measure its own **base linear velocity** (no sensor does, on any legged robot),
and in our operating mode the factory estimator that would provide it is switched **off**. Our
controller is *model-based* and **falls over within seconds without that velocity**. OptiTrack
solves this by tracking the robot's pelvis externally and giving us ground-truth base pose.

**Deliverable:** publish the robot's **base world position** (and ideally velocity) onto the DDS
topic **`rt/sportmodestate`** as a `unitree_go SportModeState_` message, at ~200 Hz, in a world
frame whose floor is `z = 0` and `z` points up. That's a **drop-in replacement** for our existing
software estimator `dds_tools/base_estimator_node.py` — same topic, same message, better data.

Get that stream working and verified, and the integration is done. Sections 4–6 are the spec.

---

## 1. The project in two minutes

We run a **Unitree H1-2 humanoid** under a **sampling Model-Predictive Controller (MJPC)**. The
goal (research paper) is sampling-MPC **on a real humanoid** for standing / leaning-to-retrieve —
the first such demonstration, characterizing sampling-vs-gradient control on real hardware.

**Component map:**

| Component | Path | Role |
|---|---|---|
| **Real robot** | Unitree H1-2 | 27 actuated joints (controller), 35 motors total; runs in low-level/debug mode |
| **MJPC controller** | `mujoco_mpc/` (task = "Lean H12") | Sampling-MPC (Predictive Sampling / CEM). **Model-based** → rolls out physics → needs full state |
| **Deploy node** | `mujoco_mpc/mujoco_mpc/mjpc/deploy/h12_control_node.cc` | Embeds the MJPC agent; subscribes to robot state over DDS, publishes joint commands. Runs **off-board on the laptop** |
| **Safety layer** | `h12_safety_layer/` | Clips commands + e-stop; relays `rt/safety/lowcmd_in` → `rt/lowcmd`. Runs **on-board (pc4)** |
| **Digital twin** | `h1_mujoco/` | MuJoCo sim of H1-2 for headless/GUI testing; in sim it *publishes* ground-truth base pose |
| **DDS tools** | `dds_tools/` | `base_estimator_node.py` (software base-state estimator), `dds_topic_check.py`, `dds_live_recorder.py` |

**Control chain (data flow):**

```
                 rt/lowstate (joints+IMU, 500Hz)   rt/sportmodestate (base pose) ← YOU (OptiTrack)
                          │                               │
                          ▼                               ▼
   MJPC node (laptop) ── reads state ── plans ── joint cmd ──► rt/safety/lowcmd_in
                                                                     │
                                                          Safety layer (pc4) clips/estops
                                                                     │
                                                                     ▼
                                                                rt/lowcmd ──► Robot (or twin)
```

All of this is **raw Unitree DDS (CycloneDDS), domain 0** — *not* ROS 2. (`ros2 topic list` cannot
see these topics; they carry no ROS graph metadata.)

---

## 2. Why OptiTrack — the actual problem

**The robot runs in low-level "debug" mode** (`MotionSwitcher.ReleaseMode`) so MJPC can command
joints directly. A side effect (Unitree-wide, closed firmware, confirmed with Unitree support):
the onboard **high-level state estimator turns off**, so the topic that would carry the base's
world pose and velocity — **`rt/sportmodestate`** — goes **silent**.

**What the robot still has:** an IMU (orientation, angular velocity, acceleration) and joint
encoders, all on `rt/lowstate`. **What it does NOT have:** base **linear velocity**. No sensor
measures absolute linear velocity on a legged robot — it must be *estimated* (even the factory
`sportmodestate.velocity` is an estimator output).

**Why that's fatal for us:** MJPC is **model-based** — it simulates the robot forward to choose
actions, so it needs the *full* floating-base state: position + orientation (`qpos[0:7]`) and
linear + angular velocity (`qvel[0:6]`). The balance/capture-point cost depends directly on base
**linear velocity**. Feed it a wrong or missing velocity and it mis-corrects and topples in
seconds. (RL controllers sidestep this — they're model-free and drop base linvel entirely. We
can't.)

**Our current stopgap:** `base_estimator_node.py` synthesizes `rt/sportmodestate` from leg
odometry + IMU (a random-walk EKF). On the twin it reached truth-parity (state RMS ≈ 0.016 m/s,
drift ≈ 7 mm / 25 s), but it still produces motion-correlated velocity spikes — a real sim-to-real
risk on hardware.

**Why OptiTrack is the gold standard:** an external camera array measures the pelvis pose
directly — ground truth, no drift, no spikes. This is **mocap-in-the-loop**, and it is exactly
what *every* published real sampling-MPC deployment that needs base velocity did:

- DIAL-MPC (real Go2) → Vicon mocap in the control loop
- RT-WholeBody-MPPI (real Go1) → OptiTrack-fused EKF
- Reference-Free MPC (real Go2) → 300 Hz mocap
- Real-H1 iLQR MPC → **OptiTrack** base velocity via LPF finite-difference of mocap position
  (authors explicitly name onboard estimation as future work)

So mocap-in-the-loop is well-precedented and **removes our biggest open risk** for the real-robot
demo.

**Two ways we'll use it:**

- **(A) Mocap-in-the-loop control** — OptiTrack → publish `rt/sportmodestate` → MJPC consumes it
  live. The real upgrade. *(This is the primary target.)*
- **(B) Offline ground-truth validation** — record OptiTrack alongside `base_estimator_node.py`
  to measure the software estimator's *true* error. Zero control risk; a good first milestone.

Both use the identical OptiTrack setup.

---

## 3. The robot rigid body — what to track

You will define **one rigid body**: the robot's **pelvis / base link** (the floating base of the
model). Practical requirements:

- **Markers on the pelvis/torso base**, rigidly mounted (no flex relative to the pelvis).
- **Asymmetric** placement so Motive can resolve orientation unambiguously.
- Positioned to **survive arm motion and self-occlusion** — the H1-2 swings its arms; markers must
  stay visible to enough cameras through the whole standing/leaning motion.
- The body must track **continuously** — dropouts feed the controller a frozen/teleporting base,
  which is worse than a noisy estimate.

Name it consistently (suggest **`h1_2_base`** or **`pelvis`**) — the consumer subscribes by name
(VRPN) and we need to know that name. Report the exact name back.

---

## 4. ★ The integration contract (read this carefully)

This is the precise spec the OptiTrack data must satisfy to plug into our controller. It is taken
from the source: `dds_tools/base_estimator_node.py` (the thing you're replacing) and
`mujoco_mpc/mujoco_mpc/mjpc/deploy/h12_control_node.cc` (the consumer, see lines ~219–240 and
~758–774).

**Transport**
- **Protocol:** raw Unitree DDS via `unitree_sdk2` / `unitree_sdk2py`, **CycloneDDS, domain 0**.
  *Not* ROS 2.
- **Topic:** **`rt/sportmodestate`**
- **Message type:** `unitree_go::msg::dds_::SportModeState_`
  - Python: `from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_`
    (construct with `unitree_go_msg_dds__SportModeState_()` from `unitree_sdk2py.idl.default`)
  - C++: `<unitree/idl/go2/SportModeState_.hpp>`
- **Rate:** ~**200 Hz** (our estimator's default). The planner runs ~50–65 Hz; mocap can run
  faster (360 Hz). Higher is fine; lower-jitter is what matters.

**Fields the controller reads** (everything else in the message is ignored)
- `msg.position[0:3]` = base world **position** `(x, y, z)` in **meters**
- `msg.velocity[0:3]` = base world **velocity** `(vx, vy, vz)` in **m/s**

**Frame / what "base position" means** — *the subtle part*
- World frame: **z-up, floor at `z = 0`** (a standing pelvis sits at `z ≈ 1.0 m`; our home keyframe
  is ≈ 1.03 m). `x` = robot **forward**. Match this when you set the OptiTrack ground plane/origin.
  **Ignore the PDF's "Sawyer / RViz +90° about X" instructions** — those are legacy for a
  different robot. Align the origin to *our* world (z-up, floor=0, x-forward).
- The position we publish is **not** the pelvis origin directly — it is the **pelvis IMU site**,
  i.e. `pelvis + R(base_quat)·IMU_OFFSET`. The node backs the pelvis out with
  `base_p = site_p − R·IMU_OFFSET`. So the bridge must publish the **IMU-site point**, *or* define
  the OptiTrack rigid-body origin at the IMU site. `IMU_OFFSET` is a fixed pelvis→IMU translation —
  get its value from `base_estimator_node.py` / the model (ask via `questions_for_main.md`).
  - *Pragmatically:* mocap gives you the rigid-body pose; apply the known static transform
    (rigid-body frame → IMU site) so the published `position` matches the convention the estimator
    used. If unsure, ask for the exact transform — getting this wrong shifts the base and the
    planner mis-balances.

**Orientation is NOT your job**
- Base **orientation** comes from the robot's **IMU** (`rt/lowstate`), *not* from
  `rt/sportmodestate`. So the minimal drop-in only needs **position** (+ velocity). OptiTrack
  *could* also supply orientation, but consuming it would require a controller change — out of
  scope for the first integration.

**Velocity is secondary**
- The node re-derives base linear velocity itself via `LPF(d/dt position)` over its clock (a
  deliberate fix for a phantom-velocity bug). So **accurate, low-latency, low-jitter `position`
  is the critical deliverable**; you may finite-difference `velocity` in the bridge or just leave
  the node to compute it. Clean position > clever velocity.

**Bottom line:** a small bridge that (1) reads the pelvis rigid-body pose from OptiTrack, (2)
transforms it to the IMU-site point in our world frame, (3) publishes
`rt/sportmodestate.position` (+ optional `.velocity`) at ~200 Hz on DDS domain 0 — is a complete
replacement for `base_estimator_node.py`.

---

## 5. ★ Network & "server" facts (everything wired-up)

There is **no DNS** here — everything is **static IPs**; use the numbers directly. There are
**two separate networks** that the bridge machine has to straddle. This is the part most likely to
bite you.

### 5a. The MoCap network (OptiTrack side)
- **Motive** runs on a dedicated **Windows PC** wired to the cameras (license sticker on the
  monitor; you generally don't touch licensing).
- **WiFi network:** `IRLab` — the streaming **client must be on the same network**.
- **Two OptiTrack systems exist:**
  - **Bigger MoCap** → Local Interface IP **`192.168.50.10`**
  - **Smaller MoCap** → **`192.168.50.24`**
  - For a standing/leaning **humanoid**, use the **bigger** system (larger capture volume) unless
    the smaller one clearly covers the workspace. Confirm which, and its IP.
- **Streaming protocols (set in Motive → Data Streaming):**
  - **VRPN** — TCP, reliable, **rigid-body only**, one client per body. Example in the PDF used
    host `tcp://192.168.50.24:3883`. Enable: Transmission Type = **Unicast**, Broadcast VRPN =
    **On**.
  - **NatNet** — UDP, all markers, may drop packets. Multicast: `client_ip = 239.255.42.99`,
    `data_port = 1511`, `comm_port = 1510`.
  - ⚠️ The lab doc notes **NatNet's Python client (`ratcave/natnetclient`) fails on Ubuntu 20.04 /
    Python 3.8 / Motive 2.2**. Check the Motive version first (`Help → About`); if it's 2.2-era,
    prefer **VRPN**.

### 5b. The robot DDS network (controller side)
- The robot is on a **separate wired subnet `192.168.123.x`**, domain 0:
  - robot onboard computer (pc4) ≈ `192.168.123.164`
  - the laptop gets `192.168.123.4` via DHCP from the robot (or set `192.168.123.99/24` manually)
  - connected through a **USB-Ethernet dongle**, NIC name like **`enx00e04c681314`** (MAC-derived;
    **read the live name** with `ip -br link` — it varies per dongle/machine).
- DDS topics on this net: `rt/lowstate`, `rt/lowcmd`, `rt/safety/lowcmd_in`, **`rt/sportmodestate`**.
- ⚠️ **Tailscale must be OFF** during robot ops. If any DDS process runs with auto-interface
  selection while `tailscale0` is up, CycloneDDS advertises the `100.x` Tailscale address into
  domain 0 and **breaks discovery with the robot** (write failures, spam, silent topics). Either
  `sudo tailscale down`, or pin the wired NIC on every DDS process.
- The raw-SDK path **ignores `CYCLONEDDS_URI`** — it builds its own config. Pin the NIC via each
  tool's flag instead: estimator/recorder `--iface <enx…>`, node `--network_interface <enx…>`,
  safety layer `network.interface` in YAML.

### 5c. Where the bridge runs (the part that straddles both)
The thing that publishes `rt/sportmodestate` must simultaneously:
1. **receive OptiTrack** over the MoCap net (`IRLab` WiFi / `192.168.50.x`), and
2. **publish DDS** on the robot net (`192.168.123.x` via the `enx` dongle).

The **laptop already has both interfaces** (WiFi for MoCap + wired `enx` for the robot), so the
bridge can run right next to the MJPC node. **Pin DDS to the `enx` NIC** so it advertises only the
wired locator into the robot's domain (and keep Tailscale down). This mirrors how
`base_estimator_node.py` already runs.

```
 OptiTrack PC (Windows/Motive)
        │  VRPN/NatNet over IRLab WiFi (192.168.50.x)
        ▼
 Laptop ── OptiTrack→DDS bridge ── publishes rt/sportmodestate
        │                              (DDS pinned to enx, domain 0)
        │  wired enx (192.168.123.x)
        ▼
 MJPC node (also on laptop) ──► safety (pc4) ──► robot
```

---

## 6. Recommended setup procedure (our specifics on top of the PDF)

Follow the PDF's Motive steps; apply these project-specific choices:

1. **Confirm Motive version** (`Help → About`) — decides VRPN vs NatNet (see §5a).
2. **Pick the system** (bigger `.10` vs smaller `.24`) by capture volume; note its IP.
3. **Calibrate the volume** — orient cameras, set a high frame rate (e.g. 360 Hz), mask
   reflections, **wand** (OptiWand, CW-500 / 500 mm), then **set ground plane + origin** with the
   CS-200 square — **aligned to our world: z-up, floor = z = 0, x = robot forward** (not the
   PDF's Sawyer convention).
4. **Define the pelvis rigid body** (see §3); name it and record the name.
5. **Enable streaming** — VRPN Unicast + Broadcast VRPN On (recommended for our non-ROS stack),
   or NatNet if you prefer all-marker UDP.
6. **Consume it on Linux** — for our **non-ROS DDS** stack, the cleanest path is a **Python VRPN
   client** (the `pyvrpn` example in the PDF: `vrpn.receiver.Tracker("<body>@tcp://<ip>:3883")`,
   returns position + quaternion) feeding a small DDS bridge that publishes `rt/sportmodestate`.
   - The PDF's "BEST WAY = ROS VRPN" (`ros-noetic-vrpn-client-ros`) is clean **only if you want
     ROS** — we don't; it would add a ROS↔DDS bridge. Prefer the Python VRPN path.
7. **Verify** the stream lands: first read raw pose with the VRPN client; once the bridge
   publishes, confirm DDS with our checker:
   `dds_tools/dds_topic_check.py --extra rt/sportmodestate` (run in the `h1_mujoco` venv; it
   auto-pins the robot NIC and reports arriving/NaN/silent + decoded values).

**Do not write the bridge yet** unless asked — first get the OptiTrack stream up, verified, and
report the facts in §10 so the main agent can spec the bridge against the exact rigid-body name,
IP, protocol, and frame.

---

## 7. Action checklist (what to actually do, in order)

1. ☐ Motive version (`Help → About`).
2. ☐ Which MoCap system + its Local Interface IP (`192.168.50.10` or `.24`).
3. ☐ Calibrate the volume (cameras → mask → wand → ground plane/origin **aligned to robot world**).
4. ☐ Mount markers on the pelvis; define + **name** the rigid body.
5. ☐ Enable streaming (VRPN Unicast recommended); note **protocol + IP + port + rigid-body name +
   rate**.
6. ☐ Read the pose from a Linux client (pyvrpn) to prove the stream works end-to-end.
7. ☐ Record the **coordinate convention** you set (where is the origin? which way is +x? units?).
8. ☐ Report everything in §10 back to the main agent.

---

## 8. Open decisions / questions to resolve

- **Marker placement** on the pelvis — rigid, asymmetric, occlusion-safe through arm motion.
- **The static transform** OptiTrack-rigid-body-frame → IMU-site / pelvis (needs `IMU_OFFSET` and
  the rigid-body origin definition). Critical — a wrong offset shifts the base.
- **Velocity:** finite-difference in the bridge or let the node do it (recommend: let the node;
  publish clean position).
- **Latency / medium:** WiFi adds jitter; for in-the-loop control prefer a wired/low-jitter path
  if available. Characterize mocap→bridge→node latency.
- **Use-case order:** do **(B) offline validation** first (no control risk), then **(A) in-loop**.

---

## 9. References

**In this repo (read for the contract):**
- `dds_tools/base_estimator_node.py` — the drop-in target (same topic/message you'll publish).
- `mujoco_mpc/mujoco_mpc/mjpc/deploy/h12_control_node.cc` — the consumer (lines ~219–240, ~758–774).
- `dds_tools/dds_topic_check.py` — verify the stream lands on DDS.
- `dds_tools/README.md` — DDS tooling notes and canonical commands.

**External (from the PDF):**
- VRPN install: `https://gist.github.com/hsharrison/24cbe284bd50973052ee` ·
  `https://github.com/vrpn/vrpn/blob/master/python_vrpn/README`
- Sarah's VRPN client guide:
  `https://github.com/sarahaguasvivas/sarahaguasvivas.github.io/blob/master/lab_notes/vrpn_client.md`
- NatNet client (Ubuntu 20.04/py3.8/Motive 2.2 caveat): `https://github.com/ratcave/natnetclient`
- ROS VRPN: `ros-noetic-vrpn-client-ros` · ROS+NatNet: `https://tuw-cpsg.github.io/tutorials/optitrack-and-ros/`
- OptiTrack skeleton wiki: `https://v22.wiki.optitrack.com/index.php?title=Skeleton_Tracking`

---

## 10. ★ Report back to the main agent (`questions_for_main.md` / status)

Fill these in and send back — they let the main agent spec the DDS bridge precisely:

1. **Motive version:** ______
2. **System used + Local Interface IP:** bigger `192.168.50.10` / smaller `192.168.50.24` → ______
3. **Streaming protocol + port:** VRPN unicast `:3883` / NatNet multicast `239.255.42.99:1511/1510`
   → ______
4. **Rigid-body name:** ______ (and number of markers, placement)
5. **Coordinate convention you set:** origin location, +x direction, units, is floor `z=0` & z-up?
6. **Stream rate:** ______ Hz
7. **Did a Linux VRPN/NatNet client read the pose successfully?** yes/no + any errors
8. **Network:** can the bridge machine reach both `192.168.50.x` (MoCap) and `192.168.123.x`
   (robot) at once? ______

**Questions to ask the main agent (high-value):**
- "What is the exact `IMU_OFFSET` (pelvis→IMU translation) and how does
  `base_estimator_node.py` map the rigid-body/site pose to the published
  `sportmodestate.position`? Paste the relevant lines."
- "Confirm the world-frame convention MJPC expects (axes, origin, units) and the home-keyframe
  base height."
- "Is there any existing OptiTrack/VRPN bridge code in the project to start from?"
- "Should the bridge publish `velocity`, or only `position` and let the node finite-difference?"

---

*This document was generated from the live project state (memory + source: `base_estimator_node.py`,
`h12_control_node.cc`, `project_real_robot_dds_connection`). The PDF covers Motive operation; this
covers why and how it plugs into our DDS/MJPC stack.*
