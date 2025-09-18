#!/usr/bin/env python3
# Defensive LED beacon for NIC activity LEDs (Ubuntu 24 + r8169):
# Sends UDP broadcast bursts to create an ON/OFF pattern visible on the ACT LED.
import argparse, socket, time, os

def run(iface, on_ms=100, off_ms=100, rate_mbps=50.0, seconds=60, port=5001):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    # Bind to the test interface so traffic egresses enp6s0
    sock.setsockopt(socket.SOL_SOCKET, 25, bytes(iface, 'utf-8') + b'\x00')  # SO_BINDTODEVICE
    payload = b"\x00" * 1400
    gap = max(1e-4, (len(payload) * 8) / (rate_mbps * 1e6))   # spacing between datagrams

    t_end = time.perf_counter() + seconds
    while time.perf_counter() < t_end:
        # ON window: send at ~rate_mbps
        t_on_end = time.perf_counter() + (on_ms / 1000.0)
        while time.perf_counter() < t_on_end:
            sock.sendto(payload, ("255.255.255.255", port))
            time.sleep(gap)
        # OFF window: silence
        time.sleep(off_ms / 1000.0)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", required=True, help="e.g., enp6s0")
    ap.add_argument("--on_ms", type=int, default=100)
    ap.add_argument("--off_ms", type=int, default=100)
    ap.add_argument("--rate_mbps", type=float, default=50.0)
    ap.add_argument("--seconds", type=int, default=60)
    args = ap.parse_args()
    run(args.iface, args.on_ms, args.off_ms, args.rate_mbps, args.seconds)
