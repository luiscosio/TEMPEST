#!/usr/bin/env python3
# Sends UDP broadcast bursts spelling 'SOS' in Morse on the ACT LED.
# Default human-friendly timing: dot=300ms, dash=900ms.
import argparse, socket, time

MORSE = {'S':'...', 'O':'---', ' ':' '}  # minimal table

def send_burst(sock, iface, ms, rate_mbps=50.0, port=5001):
    sock.setsockopt(25, bytes(iface,'utf-8') + b'\x00')  # SO_BINDTODEVICE
    payload = b'\x00'*1400
    gap = max(1e-4, (len(payload)*8)/(rate_mbps*1e6))
    t_end = time.perf_counter() + (ms/1000.0)
    while time.perf_counter() < t_end:
        sock.sendto(payload, ("255.255.255.255", port))
        time.sleep(gap)

def run(msg, iface, unit_ms, rate_mbps, repeats):
    dot = unit_ms; dash = 3*unit_ms
    intra = unit_ms        # between elements of a character
    ch_gap = 3*unit_ms     # between characters
    word_gap = 7*unit_ms   # between words
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    for _ in range(repeats):
        for ch in msg.upper():
            if ch == ' ':
                time.sleep(word_gap/1000.0); continue
            for i, sym in enumerate(MORSE.get(ch,'')):
                if sym == '.':  send_burst(s, iface, dot, rate_mbps)
                elif sym == '-': send_burst(s, iface, dash, rate_mbps)
                if i != len(MORSE[ch])-1: time.sleep(intra/1000.0)
            time.sleep(ch_gap/1000.0)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", required=True)
    ap.add_argument("--unit_ms", type=int, default=300)
    ap.add_argument("--rate_mbps", type=float, default=50.0)
    ap.add_argument("--repeats", type=int, default=6)
    args = ap.parse_args()
    run("SOS", args.iface, args.unit_ms, args.rate_mbps, args.repeats)
