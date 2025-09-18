## ETHERLED: Defensive NIC-LED Beacon + Receiver

This folder contains two pieces:
- **traffic_beacon.py**: generates short ON/OFF traffic bursts so the NIC activity LED blinks in a clean OOK pattern (no second host needed).
- **receiver_decode.py**: reads a camera recording of the LED, extracts intensity, auto-estimates bit period, and decodes/benchmarks vs an expected pattern.

Guided by 2208.09975v1, timing uses ~100 ms per bit (≈3 frames/bit at 30 fps), which is robust for camera receivers.

### Python environment
- **Python**: 3.8+
- **Packages (receiver only)**: `opencv-python`, `numpy`, `matplotlib`

#### Windows (PowerShell)
```powershell
cd ETHERLED
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install opencv-python numpy matplotlib
```

#### Linux/macOS (bash/zsh)
```bash
cd ETHERLED
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install opencv-python numpy matplotlib
```


### A) Blink the activity LED using traffic bursts

This sends UDP broadcast bursts to create ON/OFF windows (OOK) visible on the NIC ACT LED. Clean, reversible, and works without a sink host. Default timing is ON=100 ms / OFF=100 ms (≈3 frames/bit at 30 fps).

#### Install tools (Ubuntu)
```bash
sudo apt update
sudo apt install -y python3
```

Run it (root is required to bind the socket to a device):
```bash
sudo python3 traffic_beacon.py --iface enp6s0 --on_ms 100 --off_ms 100 --seconds 60
# or, if you saved the snippet:
sudo python3 traffic_beacon_broadcast.py --iface enp6s0 --on_ms 100 --off_ms 100 --seconds 60
```

You should see a clean ON 100 ms / OFF 100 ms blink on the activity LED.

If your camera struggles, lengthen windows to `--on_ms 150 --off_ms 150` to keep ≥3 frames/bit at 30 fps.

### B) Record and decode with the camera receiver

Record a 60–120 s clip per scenario (distance/mitigation) at 30 fps. Lock exposure and focus on the NIC LEDs.

Activate your environment (see above), then run:

```bash
python receiver_decode.py --video clip_30fps.mp4 --interactive-roi --auto-bit-period --plot
```

If auto-ROI misses, pass a manual ROI:

```bash
python receiver_decode.py --video clip_30fps.mp4 --roi 980,520,30,30 --auto-bit-period --plot
```

If the camera metadata FPS is wrong, override it:

```bash
python receiver_decode.py --video clip.mp4 --fps-override 30 --auto-bit-period
```

What you should see: with ON=100 ms / OFF=100 ms, the script typically estimates `bit_period ≈ 3` frames at 30 fps; BER should be near zero at short distances. This matches the paper’s finding that ~3 frames/bit is the most reliable setting for camera receivers. 2208.09975v1

#### CLI reference
```text
python receiver_decode.py --video PATH \
  [--roi x,y,w,h] [--interactive-roi] \
  [--fps-override FPS] [--bit-period N | --auto-bit-period] \
  [--expected-pattern STR] [--k-sigma K] [--detrend-win W] [--plot]
```

- **--video PATH**: Input video (required)
- **--roi x,y,w,h** or **--interactive-roi**: LED region selection
- **--fps-override FPS**: Override FPS if metadata is wrong
- **--bit-period N** or **--auto-bit-period**: Frames per bit (default 3) or estimate
- **--expected-pattern STR**: Bit string for BER (default `1010…`)
- **--k-sigma K**: Threshold = median + K·sigma (default 2.5)
- **--detrend-win W**: Moving-median window (frames)
- **--plot**: Show diagnostic plots

#### Example JSON output
```json
{
  "fps": 30.0,
  "frames": 5421,
  "roi": {"x": 316, "y": 236, "w": 28, "h": 28},
  "bit_period_frames": 3,
  "cycle_frames_est": 6,
  "offset_frames": 0,
  "ber_vs_expected": 0.0,
  "nbits_compared": 512,
  "threshold_detrended": 12.7,
  "mean_intensity_on": 210.3,
  "mean_intensity_off": 178.1,
  "on_minus_off": 32.2
}
```

### Quick troubleshooting
- **Noisy curve / missed threshold**: Increase `--k-sigma 3.0` or enlarge ROI slightly.
- **Timing drift (BER > 0.1)**: Use `--auto-bit-period` or lengthen transmit windows (e.g., `--on_ms 150 --off_ms 150`). The “3 frames/bit” guidance is robust but not mandatory. 2208.09975v1
- **Auto-ROI picks a reflection**: Use `--interactive-roi` to draw a tight box around the LED.

