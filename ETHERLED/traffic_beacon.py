#!/usr/bin/env python3
# Defensive LED beacon: generates UDP bursts to toggle the ACT LED in an OOK "1010..." pattern
import argparse, socket, time

def run(ip, port, on_ms=100, off_ms=100, rate_mbps=50, seconds=60):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = b"\x00" * 1400                        # ~MTU-sized datagram
    send_gap = max(1e-4, 1400 * 8 / (rate_mbps * 1e6))  # spacing for ~rate_mbps

    t_end = time.perf_counter() + seconds
    while time.perf_counter() < t_end:
        # ON window: saturate lightly so LED looks "solid on"
        t_on_end = time.perf_counter() + (on_ms / 1000.0)
        while time.perf_counter() < t_on_end:
            sock.sendto(payload, (ip, port))
            time.sleep(send_gap)
        # OFF window: silence
        time.sleep(off_ms / 1000.0)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip", required=True)
    ap.add_argument("--port", type=int, default=5001)
    ap.add_argument("--on_ms", type=int, default=100)   # ~3 frames at 30 fps → good decode margin
    ap.add_argument("--off_ms", type=int, default=100)
    ap.add_argument("--rate_mbps", type=float, default=50.0)
    ap.add_argument("--seconds", type=int, default=60)
    args = ap.parse_args()
    run(args.ip, args.port, args.on_ms, args.off_ms, args.rate_mbps, args.seconds)
