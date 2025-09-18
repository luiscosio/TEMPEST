#!/usr/bin/env python3
"""
Defensive NIC-LED optical analysis:
- Reads a video of a blinking NIC LED
- Extracts LED intensity from a small ROI
- Detrends + thresholds to ON/OFF
- (Optionally) auto-estimates frames-per-bit from autocorrelation
- Samples bits, aligns to 1010… pattern, reports BER and SNR

Default assumes ~3 frames/bit (≈10 bit/s at 30 fps), which ETHERLED found
to be a robust camera operating point.
"""
import cv2, numpy as np, argparse, json, math
import matplotlib.pyplot as plt

# ---------- ROI helpers ----------
def auto_roi(frame, target_percentile=99.7, pad=4):
    """Pick the smallest very bright blob (usually the LED)."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (11, 11), 0)
    thr = np.percentile(blurred, target_percentile)
    mask = (blurred >= thr).astype(np.uint8) * 255
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        raise RuntimeError("Auto-ROI failed; re-run with --interactive-roi or --roi x,y,w,h")
    cnts = sorted(cnts, key=cv2.contourArea)      # smallest bright blob
    x, y, w, h = cv2.boundingRect(cnts[0])
    x = max(0, x - pad); y = max(0, y - pad)
    w = min(frame.shape[1] - x, w + 2 * pad)
    h = min(frame.shape[0] - y, h + 2 * pad)
    return (int(x), int(y), int(w), int(h))

def select_roi(frame):
    r = cv2.selectROI("Select LED ROI (press ENTER)", frame, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow("Select LED ROI (press ENTER)")
    if r == (0,0,0,0):
        raise RuntimeError("No ROI selected.")
    return tuple(map(int, r))  # (x,y,w,h)

# ---------- Signal processing ----------
def detrend(x, win=31):
    """Moving-median detrend (odd window)."""
    w = max(3, win if win % 2 == 1 else win + 1)
    pad = w // 2
    padded = np.pad(x, (pad, pad), mode='edge')
    med = np.array([np.median(padded[i:i + w]) for i in range(len(x))])
    return x - med

def to_binary(intensity, k_sigma=2.5):
    """Threshold detrended intensity to ON/OFF using median + k*sigma."""
    mu = float(np.median(intensity))
    sigma = float(np.std(intensity)) or 1e-9
    thr = mu + k_sigma * sigma
    return (intensity > thr).astype(np.uint8), thr

def estimate_bitperiod_autocorr(signal, fps, min_ms=60, max_ms=220):
    """
    Estimate frames-per-bit from autocorrelation of the detrended intensity.
    We search the first strong peak corresponding to a full ON+OFF cycle,
    then divide by 2 to get frames/bit.
    """
    x = signal - signal.mean()
    ac = np.correlate(x, x, mode='full')[len(x)-1:]
    # search range for the full cycle (2 * bit_period)
    min_lag = max(2, int((2 * min_ms / 1000.0) * fps))
    max_lag = min(len(signal)//2, int((2 * max_ms / 1000.0) * fps))
    if max_lag <= min_lag + 1:
        return None, None
    lag = np.argmax(ac[min_lag:max_lag]) + min_lag
    cycle_frames = int(lag)
    bit_period = max(1, cycle_frames // 2)
    return bit_period, cycle_frames

def sample_bits_with_offset(frame_bits, bit_period, offset):
    """Group frame-level bits into symbol windows starting at 'offset'."""
    start = offset
    total = len(frame_bits) - start
    nbits = max(0, total // bit_period)
    bits = []
    for i in range(nbits):
        window = frame_bits[start + i*bit_period : start + (i+1)*bit_period]
        bits.append(1 if window.mean() >= 0.5 else 0)
    return bits

def best_alignment_and_ber(frame_bits, bit_period, expected_pattern):
    """Try all symbol offsets; return the offset with minimum BER."""
    exp_bits = np.array([int(c) for c in expected_pattern], dtype=np.uint8)
    best = {"offset": 0, "ber": None, "nbits": 0, "measured": []}
    for off in range(bit_period):
        bits = sample_bits_with_offset(frame_bits, bit_period, off)
        if not bits: 
            continue
        L = min(len(bits), len(exp_bits))
        if L == 0: 
            continue
        errors = int(np.sum(np.array(bits[:L]) ^ exp_bits[:L]))
        ber = errors / L
        if best["ber"] is None or ber < best["ber"]:
            best = {"offset": off, "ber": ber, "nbits": L, "measured": bits[:L]}
    return best

def roi_intensity_series(video_path, roi=None, interactive=False, fps_override=None):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if fps_override:
        fps = float(fps_override)

    ok, first = cap.read()
    if not ok:
        raise RuntimeError("Empty or unreadable video.")
    if roi is None:
        roi = select_roi(first) if interactive else auto_roi(first)
    x,y,w,h = roi

    intens = []
    def measure(frame):
        roi_img = frame[y:y+h, x:x+w]
        v = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)[:,:,2]
        return float(v.mean())

    intens.append(measure(first))
    while True:
        ok, frame = cap.read()
        if not ok: break
        intens.append(measure(frame))
    cap.release()
    return np.asarray(intens, dtype=np.float32), fps, roi

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="Path to recorded video")
    ap.add_argument("--roi", default="", help="x,y,w,h (optional)")
    ap.add_argument("--interactive-roi", action="store_true", help="Draw ROI on first frame")
    ap.add_argument("--fps-override", type=float, default=None, help="Override FPS if metadata is wrong")
    ap.add_argument("--bit-period", type=int, default=3, help="Frames per bit (default 3)")
    ap.add_argument("--auto-bit-period", action="store_true", help="Estimate frames/bit from autocorrelation")
    ap.add_argument("--expected-pattern", default="10"*512, help="Expected OOK pattern for BER (default 1010...)")
    ap.add_argument("--k-sigma", type=float, default=2.5, help="Threshold = median + k*sigma")
    ap.add_argument("--detrend-win", type=int, default=31, help="Moving-median window (frames)")
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()

    roi = tuple(map(int, args.roi.split(","))) if args.roi else None
    intens, fps, roi = roi_intensity_series(args.video, roi=roi, interactive=args.interactive_roi, fps_override=args.fps_override)
    d = detrend(intens, win=max(5, args.detrend_win | 1))
    frame_bits, thr = to_binary(d, k_sigma=args.k_sigma)

    bit_period = args.bit_period
    cycle_frames = None
    if args.auto_bit_period:
        est, cyc = estimate_bitperiod_autocorr(d, fps)
        if est is not None:
            bit_period, cycle_frames = est, cyc

    best = best_alignment_and_ber(frame_bits, bit_period, args.expected_pattern)
    # SNR estimate (simple): mean_ON - mean_OFF over frames assigned by expected pattern at best offset
    exp_bits = np.array([int(c) for c in args.expected_pattern[:best["nbits"]]], dtype=np.uint8)
    # Build a frame mask per symbol
    mask_on = np.zeros_like(frame_bits, dtype=bool)
    mask_off = np.zeros_like(frame_bits, dtype=bool)
    # Assign frames to ON/OFF using expected pattern at best offset
    start = best["offset"]
    for i in range(best["nbits"]):
        b = exp_bits[i]
        a = start + i*bit_period
        z = start + (i+1)*bit_period
        if z > len(frame_bits): break
        if b == 1: mask_on[a:z] = True
        else:      mask_off[a:z] = True

    mean_on  = float(intens[mask_on].mean())  if mask_on.any()  else float("nan")
    mean_off = float(intens[mask_off].mean()) if mask_off.any() else float("nan")
    delta = (mean_on - mean_off) if (not math.isnan(mean_on) and not math.isnan(mean_off)) else float("nan")

    report = {
        "fps": fps,
        "frames": int(len(intens)),
        "roi": {"x": roi[0], "y": roi[1], "w": roi[2], "h": roi[3]},
        "bit_period_frames": int(bit_period),
        "cycle_frames_est": int(cycle_frames) if cycle_frames else None,
        "offset_frames": int(best["offset"]),
        "ber_vs_expected": best["ber"],
        "nbits_compared": int(best["nbits"]),
        "threshold_detrended": float(thr),
        "mean_intensity_on": mean_on,
        "mean_intensity_off": mean_off,
        "on_minus_off": delta
    }
    print(json.dumps(report, indent=2))

    if args.plot:
        # Plot detrended intensity and threshold
        plt.figure()
        plt.title("ROI intensity (detrended)")
        plt.plot(d, linewidth=1)
        plt.axhline(y=thr, linestyle="--")
        plt.xlabel("Frame"); plt.ylabel("Detrended intensity")
        plt.show()

        # Plot frame-level binary signal
        plt.figure()
        plt.title("Thresholded frame-level ON/OFF")
        plt.plot(frame_bits, linewidth=1)
        plt.xlabel("Frame"); plt.ylabel("Bit (per frame)")
        plt.show()

if __name__ == "__main__":
    main()
