#!/usr/bin/env python3
"""
Morse LED beacon over UDP broadcast (defensive demo).
- Sends bursts to make the NIC activity LED blink in Morse.
- Dot = 1 unit, Dash = 3 units; intra-element gap = 1 unit;
  character gap = 3 units; word gap = 7 units.
- Default unit is 300 ms (easy to see by eye).
- Requires sudo to use SO_BINDTODEVICE and broadcast.

Usage:
  sudo python3 morse_beacon.py --iface enp6s0 --message "SOS SOS" \
       --unit-ms 300 --rate-mbps 60 --repeats 3 --verbose
"""

import argparse, socket, time, sys

MORSE_TABLE = {
    "A": ".-",   "B": "-...", "C": "-.-.", "D": "-..",  "E": ".",
    "F": "..-.", "G": "--.",  "H": "....", "I": "..",   "J": ".---",
    "K": "-.-",  "L": ".-..", "M": "--",   "N": "-.",   "O": "---",
    "P": ".--.", "Q": "--.-", "R": ".-.",  "S": "...",  "T": "-",
    "U": "..-",  "V": "...-", "W": ".--",  "X": "-..-", "Y": "-.--",
    "Z": "--..",
    "0": "-----","1": ".----","2": "..---","3": "...--","4": "....-",
    "5": ".....","6": "-....","7": "--...","8": "---..","9": "----.",
    " ": " "  # word gap
}

def bind_to_iface(sock, iface):
    # SO_BINDTODEVICE is Linux-specific; value is 25 if not exposed.
    SO_BINDTODEVICE = getattr(socket, "SO_BINDTODEVICE", 25)
    sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, iface.encode() + b"\x00")

def send_burst(sock, duration_s, rate_mbps, port, verbose=False):
    """
    Send UDP broadcast datagrams for 'duration_s' at ~rate_mbps.
    This keeps the ACT LED 'solid ON' during the window.
    """
    payload = b"\x00" * 1400
    gap = max(1e-4, (len(payload) * 8) / (rate_mbps * 1e6))  # seconds between sends
    t_end = time.perf_counter() + duration_s
    sent = 0
    while True:
        now = time.perf_counter()
        if now >= t_end:
            break
        sock.sendto(payload, ("255.255.255.255", port))
        sent += 1
        # sleep a bit, but keep loop responsive
        sleep_for = t_end - now if (t_end - now) < gap else gap
        if sleep_for > 0:
            time.sleep(sleep_for)
    if verbose:
        print(f"[ON] {duration_s*1000:.0f} ms, ~{rate_mbps:.0f} Mb/s, pkts={sent}")

def run_morse(message, iface, unit_ms, rate_mbps, repeats, port, verbose, preamble_cycles):
    unit = unit_ms / 1000.0
    dot  = unit
    dash = 3 * unit
    intra_gap = unit        # between dots/dashes within a char
    char_gap  = 3 * unit    # between characters
    word_gap  = 7 * unit    # between words

    # Socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        bind_to_iface(s, iface)
    except PermissionError:
        print("ERROR: SO_BINDTODEVICE requires sudo.", file=sys.stderr)
        sys.exit(1)

    if verbose:
        print(f"Interface    : {iface}")
        print(f"Unit (ms)    : {unit_ms} (dot), dash={3*unit_ms} ms")
        print(f"Gaps (ms)    : intra={unit_ms}, char={3*unit_ms}, word={7*unit_ms}")
        print(f"Rate (Mb/s)  : {rate_mbps}")
        print(f"Repeats      : {repeats}")
        print(f"Preamble     : {preamble_cycles} cycles of ON/OFF")
        print(f"Message      : {message}")

    # Optional preamble to help align cameras/decoders: ON 500 ms / OFF 500 ms
    for _ in range(preamble_cycles):
        send_burst(s, 0.5, rate_mbps, port, verbose=False)
        time.sleep(0.5)

    msg = message.upper()

    for r in range(repeats):
        if verbose:
            print(f"\n=== TRANSMISSION {r+1}/{repeats} ===")
        for ch in msg:
            if ch == " ":
                if verbose: print("[GAP] word gap")
                time.sleep(word_gap)
                continue
            code = MORSE_TABLE.get(ch, "")
            if not code:
                if verbose: print(f"[SKIP] unsupported char: {repr(ch)}")
                continue
            if verbose: print(f"[CHAR] {ch} -> {code}")
            for i, sym in enumerate(code):
                if sym == ".":
                    if verbose: print("  dot   (ON)", end="", flush=True)
                    send_burst(s, dot, rate_mbps, port, verbose=verbose)
                elif sym == "-":
                    if verbose: print("  dash  (ON)", end="", flush=True)
                    send_burst(s, dash, rate_mbps, port, verbose=verbose)
                # intra-element gap (OFF)
                if i != len(code) - 1:
                    if verbose: print("  gap", end="", flush=True)
                    time.sleep(intra_gap)
            # character gap (OFF)
            time.sleep(char_gap)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", required=True, help="Interface to transmit on, e.g., enp6s0")
    ap.add_argument("--message", default="SOS SOS", help="Text to send in Morse")
    ap.add_argument("--unit-ms", type=int, default=300, help="Dot length in ms (default 300)")
    ap.add_argument("--rate-mbps", type=float, default=60.0, help="Approx send rate during ON windows")
    ap.add_argument("--repeats", type=int, default=4, help="How many times to repeat the message")
    ap.add_argument("--port", type=int, default=5001, help="UDP port")
    ap.add_argument("--preamble-cycles", type=int, default=3, help="Number of ON/OFF preamble cycles")
    ap.add_argument("--verbose", action="store_true", help="Print detailed timing and symbols")
    args = ap.parse_args()
    run_morse(args.message, args.iface, args.unit_ms, args.rate_mbps,
              args.repeats, args.port, args.verbose, args.preamble_cycles)
