## ETHERLED receiver_decode.py

Minimal tool to extract LED intensity from a video, threshold it into a binary stream, sample bits at a fixed frames-per-bit rate, find a 1010 preamble, and compute BER versus an expected pattern. Optional plotting helps visualize the detrended ROI intensity.

### Requirements
- **Python**: 3.8+
- **OS**: Windows, Linux, or macOS
- **Python packages**: `opencv-python`, `numpy`, `matplotlib`

### Quick start
Below are fully isolated virtual environment setups and run commands for both Windows and Linux/macOS. Replace paths with your own.

#### Windows (PowerShell)
```powershell
cd ETHERLED
python -m venv .venv

# If activation is blocked, you may need (once):
# Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force

.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install opencv-python numpy matplotlib

# Run (basic)
python receiver_decode.py --video C:\path\to\capture.mp4 --plot

# Run with manual ROI and custom bit period
python receiver_decode.py --video C:\path\to\capture.mp4 --roi 320,240,20,20 --bit_period 3
```

#### Linux/macOS (bash/zsh)
```bash
cd ETHERLED
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install opencv-python numpy matplotlib

# Run (basic)
python receiver_decode.py --video /path/to/capture.mp4 --plot

# Run with manual ROI and custom bit period
python receiver_decode.py --video /path/to/capture.mp4 --roi 320,240,20,20 --bit_period 3
```

### Usage
```text
python receiver_decode.py --video PATH [--roi x,y,w,h] [--bit_period N] [--expected_pattern STR] [--plot]
```

- **--video PATH**: Path to the recorded video (required).
- **--roi x,y,w,h**: Optional manual ROI; if omitted, auto-ROI selects a small bright blob.
- **--bit_period N**: Frames per bit (default: 3), per ETHERLED guidance.
- **--expected_pattern STR**: Bit string used to compute BER (default: 1010 repeated).
- **--plot**: Show a plot of detrended ROI intensity with the threshold line.

### What it does
1. Loads the video and determines FPS.
2. Finds the LED ROI automatically (or uses your manual ROI).
3. Extracts mean brightness per frame from the ROI and detrends it.
4. Thresholds to a binary stream and samples bits at `--bit_period` frames per bit.
5. Searches for `1010` preamble and previews following payload bits.
6. Computes BER vs `--expected_pattern` and prints a JSON report.

### Example output
```json
{
  "fps": 30.0,
  "roi": [316, 236, 28, 28],
  "frames": 5421,
  "bit_period_frames": 3,
  "threshold": 12.7,
  "preamble_index": 48,
  "payload_preview_bits": "1010010110...",
  "ber_vs_expected": 0.03125
}
```

### Tips
- If auto-ROI fails on low-contrast footage, specify `--roi x,y,w,h` manually.
- If the video cannot be opened, verify the path, file permissions, and codec support.
- Use `--plot` to verify that the threshold line reasonably separates ON/OFF levels.


