#!/usr/bin/env python3
"""pose_udp_bridge.py -- receive pelvis pose by unicast UDP, publish rt/sportmodestate on DDS.

THE NO-MCP, NO-WIRE-ON-THE-PC PATH. DDS over WiFi does not work here (DDS discovery is
multicast, which the lab AP and the robot's own AP both block -- verified). But UNICAST crosses
WiFi fine (ping works). So:

  Motive PC (publish_sportmodestate.py, UDP_SINK="<this-laptop-ip>:9870")
      --unicast UDP over WiFi-->  THIS bridge (on the laptop, on the robot's WIRED 192.168.123.x)
      --DDS on the wire-->  rt/sportmodestate, next to rt/lowstate, for the MJPC node.

Packet = b"MCAP" + struct("<7d", t, px,py,pz, vx,vy,vz)  (site-world pose + velocity).

RUN (on the box that is WIRED to the robot's 192.168.123.x net, with unitree_sdk2py installed):
  python pose_udp_bridge.py --iface <robot-net-NIC> --port 9870
  #   e.g. --iface enx00e04c681314  (a USB-ethernet adapter on the robot's 192.168.123.x subnet)
  # On the Motive PC set CONFIG UDP_SINK = "<this-box-ip>:9870" so the publisher sends pose here.
VERIFY (another terminal on this box):
  dds_topic_check.py --robot-ip 192.168.123.161   # rt/sportmodestate now next to rt/lowstate
"""
import argparse
import socket
import struct
import time

MAGIC = b"MCAP"
PKT = struct.Struct("<7d")   # t, px, py, pz, vx, vy, vz


def main():
    ap = argparse.ArgumentParser(description="Unicast-UDP pose -> DDS rt/sportmodestate bridge.")
    ap.add_argument("--bind", default="0.0.0.0", help="UDP listen address")
    ap.add_argument("--port", type=int, default=9870, help="UDP port (match the PC's UDP_SINK)")
    ap.add_argument("--iface", default="enx00e04c681314", help="DDS NIC on the robot's WIRED subnet")
    ap.add_argument("--domain", type=int, default=0)
    ap.add_argument("--out-topic", default="rt/sportmodestate")
    ap.add_argument("--hold-timeout", type=float, default=0.5,
                    help="if no UDP for this long, publish nothing (consumer sees it go silent)")
    ap.add_argument("--selftest", action="store_true", help="offline pack/import check, then exit")
    a = ap.parse_args()

    if a.selftest:
        b = MAGIC + PKT.pack(1.0, 1.0, 2.0, 3.0, 0.1, 0.2, 0.3)
        assert b[:4] == MAGIC and len(b) == 4 + PKT.size
        t, px, py, pz, vx, vy, vz = PKT.unpack(b[4:])
        assert (px, py, pz) == (1.0, 2.0, 3.0) and (vx, vy, vz) == (0.1, 0.2, 0.3)
        print(f"[selftest] packet round-trip : PASS  (size {len(b)} bytes)")
        import importlib
        for m in ("unitree_sdk2py.core.channel",
                  "unitree_sdk2py.idl.unitree_go.msg.dds_",
                  "unitree_sdk2py.idl.default"):
            importlib.import_module(m)
        print("[selftest] unitree imports   : PASS")
        print("[selftest] PASS")
        return

    from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher
    from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_
    from unitree_sdk2py.idl.default import unitree_go_msg_dds__SportModeState_
    ChannelFactoryInitialize(a.domain, a.iface)
    pub = ChannelPublisher(a.out_topic, SportModeState_)
    pub.Init()
    msg = unitree_go_msg_dds__SportModeState_()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((a.bind, a.port))
    sock.settimeout(a.hold_timeout)
    print(f"[udp-bridge] UDP {a.bind}:{a.port}  ->  DDS '{a.out_topic}' on {a.iface} (domain {a.domain})",
          flush=True)
    print("[udp-bridge] waiting for pose packets... (Ctrl+C to stop)", flush=True)

    n = 0
    t0 = time.time()
    while True:
        try:
            data, addr = sock.recvfrom(256)
        except socket.timeout:
            continue                       # no pose lately -> publish nothing (consumer goes silent)
        except KeyboardInterrupt:
            print("\n[udp-bridge] stopping", flush=True)
            break
        if len(data) < 4 + PKT.size or data[:4] != MAGIC:
            continue
        t, px, py, pz, vx, vy, vz = PKT.unpack(data[4:4 + PKT.size])
        msg.position[0], msg.position[1], msg.position[2] = px, py, pz
        msg.velocity[0], msg.velocity[1], msg.velocity[2] = vx, vy, vz
        pub.Write(msg)
        n += 1
        if n % 100 == 0:
            print(f"[udp-bridge] {time.time()-t0:6.1f}s  from {addr[0]}  "
                  f"pos=[{px:+.3f},{py:+.3f},{pz:+.3f}]  vel=[{vx:+.3f},{vy:+.3f},{vz:+.3f}]", flush=True)


if __name__ == "__main__":
    main()
