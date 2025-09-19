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
    """Bind socket to specific interface."""
    # SO_BINDTODEVICE is Linux-specific; value is 25 if not exposed.
    SO_BINDTODEVICE = getattr(socket, "SO_BINDTODEVICE", 25)
    try:
        sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, iface.encode() + b"\x00")
    except OSError as e:
        if e.errno == 19:  # ENODEV - No such device
            print(f"ERROR: Interface '{iface}' not found.", file=sys.stderr)
            sys.exit(1)
        elif e.errno == 1:  # EPERM - Operation not permitted
            print("ERROR: SO_BINDTODEVICE requires sudo.", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"ERROR: Failed to bind to interface '{iface}': {e}", file=sys.stderr)
            sys.exit(1)

def send_burst(sock, duration_s, rate_mbps, port, verbose=False):
    """
    Send UDP broadcast datagrams for 'duration_s' at ~rate_mbps.
    This keeps the ACT LED 'solid ON' during the window.
    """
    payload = b"\x00" * 1400
    packet_bits = len(payload) * 8
    packet_interval = packet_bits / (rate_mbps * 1e6)  # seconds between packets
    
    start_time = time.perf_counter()
    end_time = start_time + duration_s
    next_send = start_time
    sent = 0
    
    while time.perf_counter() < end_time:
        current_time = time.perf_counter()
        
        # Send packet if it's time
        if current_time >= next_send:
            try:
                sock.sendto(payload, ("255.255.255.255", port))
                sent += 1
                next_send += packet_interval
            except OSError as e:
                if verbose:
                    print(f"Warning: sendto failed: {e}", file=sys.stderr)
        
        # Sleep until next packet or end of burst
        sleep_until = min(next_send, end_time)
        sleep_duration = sleep_until - time.perf_counter()
        if sleep_duration > 0:
            time.sleep(sleep_duration)
    
    if verbose:
        actual_duration = time.perf_counter() - start_time
        actual_rate = (sent * packet_bits) / (actual_duration * 1e6)
        print(f"  [ON] {actual_duration*1000:.0f} ms, {actual_rate:.1f} Mb/s, pkts={sent}")

def run_morse(message, iface, unit_ms, rate_mbps, repeats, port, verbose, preamble_cycles):
    unit = unit_ms / 1000.0
    dot  = unit
    dash = 3 * unit
    intra_gap = unit        # between dots/dashes within a char
    char_gap  = 3 * unit    # between characters
    word_gap  = 7 * unit    # between words

    # Socket setup with error handling
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        bind_to_iface(s, iface)
    except Exception as e:
        print(f"ERROR: Failed to setup socket: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if verbose:
            print(f"Interface    : {iface}")
            print(f"Unit (ms)    : {unit_ms} (dot), dash={3*unit_ms} ms")
            print(f"Gaps (ms)    : intra={unit_ms}, char={3*unit_ms}, word={7*unit_ms}")
            print(f"Rate (Mb/s)  : {rate_mbps}")
            print(f"Repeats      : {repeats}")
            print(f"Preamble     : {preamble_cycles} cycles of ON/OFF")
            print(f"Message      : {message}")

        # Optional preamble to help align cameras/decoders: ON 500 ms / OFF 500 ms
        if preamble_cycles > 0:
            if verbose:
                print("\n=== PREAMBLE ===")
            for i in range(preamble_cycles):
                if verbose:
                    print(f"Cycle {i+1}/{preamble_cycles}: ON")
                send_burst(s, 0.5, rate_mbps, port, verbose=False)
                if verbose:
                    print(f"Cycle {i+1}/{preamble_cycles}: OFF")
                time.sleep(0.5)

        msg = message.upper()

        for r in range(repeats):
            if verbose:
                print(f"\n=== TRANSMISSION {r+1}/{repeats} ===")
            
            for ch_idx, ch in enumerate(msg):
                if ch == " ":
                    if verbose: 
                        print("[GAP] word gap (7 units)")
                    time.sleep(word_gap)
                    continue
                
                code = MORSE_TABLE.get(ch, "")
                if not code:
                    if verbose: 
                        print(f"[SKIP] unsupported char: {repr(ch)}")
                    continue
                
                if verbose: 
                    print(f"[CHAR] {ch} -> {code}")
                
                # Send each symbol in the character
                for i, sym in enumerate(code):
                    # Track timing to compensate for send_burst duration
                    symbol_start = time.perf_counter()
                    
                    if sym == ".":
                        if verbose: 
                            print("  dot  ", end="", flush=True)
                        send_burst(s, dot, rate_mbps, port, verbose=verbose)
                        target_duration = dot
                    elif sym == "-":
                        if verbose: 
                            print("  dash ", end="", flush=True)
                        send_burst(s, dash, rate_mbps, port, verbose=verbose)
                        target_duration = dash
                    else:
                        continue
                    
                    # Intra-element gap (between symbols in same character)
                    if i < len(code) - 1:
                        elapsed = time.perf_counter() - symbol_start
                        gap_duration = max(0, target_duration + intra_gap - elapsed)
                        if gap_duration > 0:
                            if verbose: 
                                print(f"  [gap {gap_duration*1000:.0f}ms]")
                            time.sleep(gap_duration)
                
                # Character gap (between characters)
                # Don't add extra gap after last character of message
                if ch_idx < len(msg) - 1 and (ch_idx + 1 >= len(msg) or msg[ch_idx + 1] != " "):
                    if verbose:
                        print(f"[CHAR GAP] {char_gap*1000:.0f}ms")
                    time.sleep(char_gap)
            
            # Gap between repeats
            if r < repeats - 1:
                if verbose:
                    print(f"[REPEAT GAP] {word_gap*1000:.0f}ms")
                time.sleep(word_gap)
                
    finally:
        s.close()
        if verbose:
            print("\n=== TRANSMISSION COMPLETE ===")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Morse code LED beacon using UDP broadcasts")
    ap.add_argument("--iface", required=True, help="Interface to transmit on, e.g., enp6s0")
    ap.add_argument("--message", default="SOS SOS", help="Text to send in Morse (default: 'SOS SOS')")
    ap.add_argument("--unit-ms", type=int, default=300, help="Dot length in ms (default: 300)")
    ap.add_argument("--rate-mbps", type=float, default=60.0, help="Approx send rate during ON windows (default: 60)")
    ap.add_argument("--repeats", type=int, default=4, help="How many times to repeat the message (default: 4)")
    ap.add_argument("--port", type=int, default=5001, help="UDP port (default: 5001)")
    ap.add_argument("--preamble-cycles", type=int, default=3, help="Number of ON/OFF preamble cycles (default: 3)")
    ap.add_argument("--verbose", action="store_true", help="Print detailed timing and symbols")
    args = ap.parse_args()
    
    try:
        run_morse(args.message, args.iface, args.unit_ms, args.rate_mbps,
                  args.repeats, args.port, args.verbose, args.preamble_cycles)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(0)