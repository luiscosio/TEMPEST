# receiver_decode.py
# Defensive NIC-LED optical analysis: ROI intensity extraction + OOK decoder with 1010 preamble.
# Uses fixed bit_period_frames (default=3) per ETHERLED’s “three frames per bit” guidance. :contentReference[oaicite:17]{index=17}
import cv2, numpy as np, argparse, json, math
import matplotlib.pyplot as plt

def read_video(path):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok: break
        frames.append(frame)
    cap.release()
    return np.array(frames), float(fps)

def auto_roi(frame, target_percentile=99.7, pad=4):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (11,11), 0)
    thr = np.percentile(blurred, target_percentile)
    mask = (blurred >= thr).astype(np.uint8) * 255
    cnts,_ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        raise RuntimeError("Auto-ROI failed; supply --roi x,y,w,h")
    # pick smallest bright blob (often the LED, not a reflection panel)
    cnts = sorted(cnts, key=cv2.contourArea)  
    x,y,w,h = cv2.boundingRect(cnts[0])
    x = max(0, x-pad); y = max(0, y-pad)
    w = min(frame.shape[1]-x, w+2*pad); h = min(frame.shape[0]-y, h+2*pad)
    return (x,y,w,h)

def series_from_roi(frames, roi):
    x,y,w,h = roi
    vals = []
    for f in frames:
        roi_img = f[y:y+h, x:x+w]
        v = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)[:,:,2]  # value channel
        vals.append(float(v.mean()))
    return np.asarray(vals)

def detrend(x, win=31):
    # moving-median detrend (odd window)
    w = max(3, win if win%2==1 else win+1)
    pad = w//2
    padded = np.pad(x, (pad,pad), mode='edge')
    med = np.array([np.median(padded[i:i+w]) for i in range(len(x))])
    return x - med

def to_binary(intensity, k=3.0):
    mu = float(np.median(intensity))
    sigma = float(np.std(intensity))
    thr = mu + k*sigma
    return (intensity > thr).astype(np.uint8), thr

def sample_bits(bitstream, bit_period_frames=3):
    nbits = len(bitstream)//bit_period_frames
    bits = []
    for i in range(nbits):
        window = bitstream[i*bit_period_frames:(i+1)*bit_period_frames]
        bits.append(1 if window.mean() >= 0.5 else 0)
    return bits

def find_preamble(bits, preamble=[1,0,1,0]):
    for i in range(0, len(bits)-len(preamble)):
        if bits[i:i+len(preamble)] == preamble:
            return i
    return -1

def ber(measured, expected):
    L = min(len(measured), len(expected))
    if L == 0: return None
    errors = sum(int(measured[i]!=expected[i]) for i in range(L))
    return errors / L

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="Path to recorded video")
    ap.add_argument("--roi", default="", help="x,y,w,h manual ROI (optional)")
    ap.add_argument("--bit_period", type=int, default=3, help="frames per bit (default 3 per ETHERLED)")
    ap.add_argument("--expected_pattern", default="1010"*256, help="expected OOK bit pattern for BER")
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()

    frames, fps = read_video(args.video)
    first = frames[0]
    if args.roi:
        x,y,w,h = map(int, args.roi.split(","))
        roi = (x,y,w,h)
    else:
        roi = auto_roi(first)

    intens = series_from_roi(frames, roi)
    d = detrend(intens, win=max(5, int(fps//1)|1))
    bits_raw, thr = to_binary(d, k=2.5)
    bits = sample_bits(bits_raw, args.bit_period)

    # locate preamble 1010 (from Fig. 5) then read next 64 bits for demonstration. :contentReference[oaicite:18]{index=18}
    preamble = [1,0,1,0]
    idx = find_preamble(bits, preamble)
    payload_bits = bits[idx+len(preamble):idx+len(preamble)+64] if idx >= 0 else []

    expected = [int(c) for c in args.expected_pattern[:len(bits)]]
    bit_error_rate = ber(bits, expected)

    report = {
        "fps": fps,
        "roi": roi,
        "frames": len(frames),
        "bit_period_frames": args.bit_period,
        "threshold": thr,
        "preamble_index": idx,
        "payload_preview_bits": "".join(map(str, payload_bits[:32])),
        "ber_vs_expected": bit_error_rate
    }
    print(json.dumps(report, indent=2))

    if args.plot:
        plt.figure()
        plt.title("ROI intensity (detrended)")
        plt.plot(d)
        plt.axhline(y=thr, linestyle="--")
        plt.show()

if __name__ == "__main__":
    main()
