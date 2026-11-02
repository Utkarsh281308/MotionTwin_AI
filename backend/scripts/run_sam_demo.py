"""Live SAM 3.1 test on the synthetic demo video, scored against the known true positions.

Usage (from backend/):
  .venv/bin/python scripts/run_sam_demo.py                 # frames mode (default): ~600 images ≈ $1.50
  .venv/bin/python scripts/run_sam_demo.py --mode video    # whole-video mode: 600 frames ≈ $0.12
  .venv/bin/python scripts/run_sam_demo.py --reuse         # re-analyse the saved output, no API call
  .venv/bin/python scripts/run_sam_demo.py --prompt "brown box"
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.models import Track, Zone  # noqa: E402
from app.simulation.model_builder import build_process_model  # noqa: E402
from app.vision.meta_sam import (  # noqa: E402
    parse_sam_output, read_video_info, request_sam_frames, request_sam_video, tracks_from_frame_outputs,
)
from app.vision.zone_events import extract_zone_events  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
VIDEO = ROOT / "sample_data" / "videos" / "demo_parcel_line.mp4"
RAW = ROOT / "sample_data" / "ground_truth" / "demo_sam_raw.json"
DEMO = json.loads((ROOT / "sample_data" / "ground_truth" / "demo_tracks.json").read_text())
TRUTH = json.loads((ROOT / "sample_data" / "ground_truth" / "demo_ground_truth.json").read_text())
PROMPT = sys.argv[sys.argv.index("--prompt") + 1] if "--prompt" in sys.argv else "brown box"

MODE = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "frames"
RAW = RAW.with_name(f"demo_sam_raw_{MODE}.json")

if "--reuse" in sys.argv:
    saved = json.loads(RAW.read_text())
else:
    print(f"Sending {VIDEO.name} to SAM 3.1 ({MODE} mode) with prompt '{PROMPT}' ...")
    if MODE == "video":
        saved = {"prompt": PROMPT, "raw": request_sam_video(str(VIDEO), PROMPT)}
    else:
        stride, raw_frames = request_sam_frames(str(VIDEO), PROMPT)
        saved = {"prompt": PROMPT, "stride": stride, "raw": raw_frames}
    RAW.write_text(json.dumps(saved))
    print(f"Saved raw output to {RAW}")

if MODE == "video":
    sam_tracks = parse_sam_output(saved["raw"], label=saved["prompt"])
else:
    raw_frames = {int(k): v for k, v in saved["raw"].items()}
    print(f"{len(raw_frames)} images, {sum(1 for v in raw_frames.values() if v)} with detections")
    sam_tracks = tracks_from_frame_outputs(raw_frames, saved["stride"], label=saved["prompt"])
true_tracks = [Track(**t) for t in DEMO["tracks"]]
fps = read_video_info(str(VIDEO))[0]

# --- 1. Tracking quality: match each SAM track to the nearest true track
true_pos = {t.track_id: {p.frame: (p.x, p.y) for p in t.points} for t in true_tracks}
errors, matched = [], {}
for st in sam_tracks:
    best, best_err = None, float("inf")
    for tid, pos in true_pos.items():
        d = [np.hypot(p.x - pos[p.frame][0], p.y - pos[p.frame][1]) for p in st.points if p.frame in pos]
        if len(d) >= len(st.points) * 0.8 and np.mean(d) < best_err:
            best, best_err = tid, float(np.mean(d))
    if best is not None:
        matched.setdefault(best, []).append(st.track_id)
        errors.append(best_err)

detected = sum(len(t.points) for t in sam_tracks)
expected = sum(len(t.points) for t in true_tracks)
print("\n== Tracking ==")
print(f"objects: SAM found {len(sam_tracks)} tracks, truth has {len(true_tracks)}")
print(f"detections: {detected} of {expected} object-frames ({detected / expected:.0%})")
print(f"position error: mean {np.mean(errors):.1f}px" if errors else "no tracks matched")
split = {k: v for k, v in matched.items() if len(v) > 1}
print(f"true parcels split into several SAM ids: {len(split)} {split if split else ''}")
print(f"unmatched SAM tracks: {len(sam_tracks) - sum(len(v) for v in matched.values())}")

# --- 2. What matters for MotionTwin: station timings
zones = [Zone(**z) for z in DEMO["zones"]]
events = extract_zone_events(sam_tracks, zones, fps)
model = build_process_model(events, zones, DEMO["duration"])
print("\n== Station timings (SAM tracks vs ground truth) ==")
for st, key in zip(model.stations, ["a_service", "b_service"]):
    true_mean = np.mean([t[key] for t in TRUTH])
    est = np.mean(st.service_times)
    print(f"{st.name}: {len(st.service_times)} visits, measured {est:.2f}s vs true {true_mean:.2f}s "
          f"({(est - true_mean) / true_mean:+.0%})")
print(f"mean gap between arrivals: {np.mean(model.interarrival_times):.2f}s "
      f"(true {np.mean(np.diff([t['arrival'] for t in TRUTH])):.2f}s)")
print(f"completed parcels: {model.observed_completed} (true {sum(t['completed'] for t in TRUTH)})")
