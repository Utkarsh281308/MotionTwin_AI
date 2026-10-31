"""Generate a synthetic 2-station parcel line (tracks + ground truth) for demos and tests.

Station A (scan) ~2.5s, Station B (pack) ~3.7s, a parcel arrives every ~3s,
so Station B is the bottleneck and its queue grows. Queues sit OUTSIDE the zones.
"""
import json
import random
from pathlib import Path

FPS, W, H, DURATION = 10, 640, 360, 60.0
Y = 180
QA_X, A_X, QB_X, B_X = 120, 200, 380, 450
OUT = Path(__file__).resolve().parents[2] / "sample_data" / "ground_truth"


def rect(x0, y0, x1, y1):
    return [{"x": x0, "y": y0}, {"x": x1, "y": y0}, {"x": x1, "y": y1}, {"x": x0, "y": y1}]


def interp(keys, t):
    for (t0, x0), (t1, x1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            return x0 if t1 == t0 else x0 + (x1 - x0) * (t - t0) / (t1 - t0)
    return None


def main(seed: int = 7):
    rng = random.Random(seed)
    tracks, truth = [], []
    t, a_free, b_free, i = 0.0, 0.0, 0.0, 0
    while t < DURATION:
        spawn = t
        at_qa = spawn + 1.0
        a_start = max(at_qa, a_free)
        a_end = a_start + 0.2 + rng.uniform(2.0, 3.0)
        a_free = a_end
        at_qb = a_end + 1.5
        b_start = max(at_qb, b_free)
        b_end = b_start + 0.2 + rng.uniform(3.2, 4.2)
        b_free = b_end
        gone = b_end + 1.0
        keys = [(spawn, 0), (at_qa, QA_X), (a_start, QA_X), (a_start + 0.2, A_X), (a_end, A_X),
                (at_qb, QB_X), (b_start, QB_X), (b_start + 0.2, B_X), (b_end, B_X), (gone, W)]
        pts = []
        for f in range(int(spawn * FPS), int(min(gone, DURATION) * FPS) + 1):
            x = interp(keys, f / FPS)
            if x is not None:
                pts.append({"frame": f, "x": round(x, 1), "y": Y + rng.uniform(-3, 3)})
        tracks.append({"track_id": i, "label": "parcel", "points": pts})
        truth.append({"track_id": i, "a_service": a_end - a_start - 0.2, "b_service": b_end - b_start - 0.2,
                      "arrival": at_qa, "completed": b_end <= DURATION})
        t += rng.uniform(2.5, 3.5)
        i += 1

    zones = [
        {"id": "A", "name": "Scan station", "polygon": rect(170, 150, 230, 210), "capacity": 1, "order": 0},
        {"id": "B", "name": "Pack station", "polygon": rect(420, 150, 480, 210), "capacity": 1, "order": 1},
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "demo_tracks.json").write_text(json.dumps(
        {"fps": FPS, "width": W, "height": H, "duration": DURATION, "zones": zones, "tracks": tracks}))
    (OUT / "demo_ground_truth.json").write_text(json.dumps(truth, indent=1))
    print(f"wrote {len(tracks)} tracks to {OUT}")


if __name__ == "__main__":
    main()
