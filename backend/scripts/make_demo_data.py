"""Generate a synthetic 2-station parcel line: tracks, ground truth and an MP4 video.

Station A (scan) ~2.5s, Station B (pack) ~3.7s, a parcel arrives every ~3s,
so Station B is the bottleneck and its queue grows. Queues sit OUTSIDE the zones,
and waiting parcels line up one behind another (so a tracker can tell them apart).

Usage (from backend/):  .venv/bin/python scripts/make_demo_data.py [--video]
"""
import json
import random
import sys
from pathlib import Path

FPS, W, H, DURATION = 10, 640, 360, 60.0
Y = 180
QA_X, A_X, QB_X, B_X = 120, 200, 440, 530  # front of queue A, station A, front of queue B, station B
SLOT = 32  # spacing between waiting parcels
SHUFFLE = 0.4  # seconds for a queue to slide forward one place
MOVE = 0.2  # seconds to step into / out of a station
STEP_OUT = 60  # pixels a box moves when stepping out of a station (clears the zone)
CLEAR = 0.6  # a station is free only once the previous box has left it
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sample_data" / "ground_truth"
VIDEO = ROOT / "sample_data" / "videos" / "demo_parcel_line.mp4"


def rect(x0, y0, x1, y1):
    return [{"x": x0, "y": y0}, {"x": x1, "y": y0}, {"x": x1, "y": y1}, {"x": x0, "y": y1}]


def lerp(x0, x1, t0, t1, t):
    return x0 + (x1 - x0) * (t - t0) / (t1 - t0)


def schedule(rng):
    """FIFO timings for each parcel through queue A -> A -> queue B -> B."""
    items, t, a_free, b_free = [], 0.0, 0.0, 0.0
    while t < DURATION:
        it = {"spawn": t, "at_qa": t + 1.0}
        it["a_start"] = max(it["at_qa"], a_free)
        it["a_service"] = rng.uniform(2.0, 3.0)
        it["a_end"] = it["a_start"] + MOVE + it["a_service"]
        a_free = it["a_end"] + CLEAR
        it["at_qb"] = it["a_end"] + 1.5
        it["b_start"] = max(it["at_qb"], b_free)
        it["b_service"] = rng.uniform(3.2, 4.2)
        it["b_end"] = it["b_start"] + MOVE + it["b_service"]
        b_free = it["b_end"] + CLEAR
        it["gone"] = it["b_end"] + 1.0
        items.append(it)
        t += rng.uniform(2.5, 3.5)
    return items


def waiting_ahead(items, i, t, arrive, start):
    """How many earlier parcels are still in the same queue (or stepping out of it) at time t."""
    return sum(1 for j in range(i) if items[j][arrive] <= t < items[j][start] + MOVE)


def queue_x(items, i, t, front, arrive, start):
    """Spot in the queue at time t. Boxes slide forward over SHUFFLE seconds instead of teleporting.

    Boxes still walking to the queue head for this same smoothed spot, so they never run into
    the box ahead while it is still sliding forward.
    """
    ahead = sum(waiting_ahead(items, i, t - SHUFFLE * k / 4, arrive, start) for k in range(5)) / 5
    return front - SLOT * ahead


def position(items, i, t):
    it = items[i]
    if t < it["spawn"] or t > it["gone"]:
        return None
    if t < it["at_qa"]:
        slot = queue_x(items, i, t, QA_X, "at_qa", "a_start")
        return lerp(0, slot, it["spawn"], it["at_qa"], t)
    if t < it["a_start"]:
        return queue_x(items, i, t, QA_X, "at_qa", "a_start")
    if t < it["a_start"] + MOVE:
        return lerp(QA_X, A_X, it["a_start"], it["a_start"] + MOVE, t)
    if t < it["a_end"]:
        return A_X
    if t < it["a_end"] + MOVE:
        return lerp(A_X, A_X + STEP_OUT, it["a_end"], it["a_end"] + MOVE, t)
    if t < it["at_qb"]:
        slot = queue_x(items, i, t, QB_X, "at_qb", "b_start")
        return lerp(A_X + STEP_OUT, slot, it["a_end"] + MOVE, it["at_qb"], t)
    if t < it["b_start"]:
        return queue_x(items, i, t, QB_X, "at_qb", "b_start")
    if t < it["b_start"] + MOVE:
        return lerp(QB_X, B_X, it["b_start"], it["b_start"] + MOVE, t)
    if t < it["b_end"]:
        return B_X
    if t < it["b_end"] + MOVE:
        return lerp(B_X, B_X + STEP_OUT, it["b_end"], it["b_end"] + MOVE, t)
    return lerp(B_X + STEP_OUT, W + 20, it["b_end"] + MOVE, it["gone"], t)


def render_video(zones, frames):
    """Top-down view: grey floor, coloured station mats, cardboard boxes."""
    import cv2
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.vision.video_io import to_browser_mp4

    VIDEO.parent.mkdir(parents=True, exist_ok=True)
    raw = VIDEO.with_suffix(".raw.mp4")
    writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    floor = np.full((H, W, 3), 190, np.uint8)
    cv2.rectangle(floor, (0, Y - 30), (W, Y + 30), (150, 150, 150), -1)  # walkway
    for z, colour in zip(zones, [(200, 140, 60), (80, 170, 80)]):
        p = z["polygon"]
        cv2.rectangle(floor, (p[0]["x"] - 10, p[0]["y"] - 10), (p[2]["x"] + 10, p[2]["y"] + 10), colour, -1)
        cv2.putText(floor, z["name"].split()[0].upper(), (p[0]["x"] - 8, p[0]["y"] - 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (40, 40, 40), 2)
    for boxes in frames:
        img = floor.copy()
        for x, y in boxes:
            x, y = int(x), int(y)
            cv2.rectangle(img, (x - 13, y - 11), (x + 13, y + 11), (60, 120, 180), -1)  # cardboard (BGR)
            cv2.rectangle(img, (x - 13, y - 11), (x + 13, y + 11), (30, 70, 110), 2)
            cv2.line(img, (x, y - 11), (x, y + 11), (140, 200, 230), 3)  # tape
        writer.write(img)
    writer.release()
    to_browser_mp4(str(raw), str(VIDEO))  # H.264 so browsers can play it
    raw.unlink()
    print(f"wrote {VIDEO} ({len(frames)} frames, H.264)")


def main(seed: int = 7, video: bool = False):
    rng = random.Random(seed)
    items = schedule(rng)
    n_frames = int(DURATION * FPS)
    jitter = [[rng.uniform(-3, 3) for _ in range(n_frames)] for _ in items]

    tracks = [{"track_id": i, "label": "parcel", "points": []} for i in range(len(items))]
    frames = []
    for f in range(n_frames):
        boxes = []
        for i in range(len(items)):
            x = position(items, i, f / FPS)
            if x is not None and x <= W:
                y = Y + jitter[i][f]
                tracks[i]["points"].append({"frame": f, "x": round(x, 1), "y": round(y, 1)})
                boxes.append((x, y))
        frames.append(boxes)

    truth = [{"track_id": i, "a_service": it["a_service"], "b_service": it["b_service"],
              "arrival": it["at_qa"], "completed": it["b_end"] <= DURATION} for i, it in enumerate(items)]
    zones = [
        {"id": "A", "name": "Scan station", "polygon": rect(170, 150, 230, 210), "capacity": 1, "order": 0},
        {"id": "B", "name": "Pack station", "polygon": rect(500, 150, 560, 210), "capacity": 1, "order": 1},
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "demo_tracks.json").write_text(json.dumps(
        {"fps": FPS, "width": W, "height": H, "duration": DURATION, "zones": zones, "tracks": tracks}))
    (OUT / "demo_ground_truth.json").write_text(json.dumps(truth, indent=1))
    print(f"wrote {len(tracks)} tracks to {OUT}")
    if video:
        render_video(zones, frames)


if __name__ == "__main__":
    main(video="--video" in sys.argv)
