"""End-to-end on the synthetic demo: tracks -> events -> model -> simulation vs ground truth."""
import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from app.main import app

GT = Path(__file__).resolve().parents[2] / "sample_data" / "ground_truth" / "demo_ground_truth.json"
client = TestClient(app)


def test_demo_pipeline_recovers_ground_truth():
    session = client.post("/api/demo/load").json()
    r = client.post(f"/api/sessions/{session['id']}/model")
    assert r.status_code == 200, r.text
    model = r.json()["model"]

    truth = json.loads(GT.read_text())
    true_a = np.mean([t["a_service"] for t in truth])
    true_b = np.mean([t["b_service"] for t in truth])
    est_a = np.mean(model["stations"][0]["service_times"])
    est_b = np.mean(model["stations"][1]["service_times"])
    assert abs(est_a - true_a) / true_a < 0.15
    assert abs(est_b - true_b) / true_b < 0.15

    sim = client.post("/api/simulate", json={
        "model": model,
        "scenario": {"name": "faster packing", "station_changes": [{"zone_id": "B", "speed_factor": 1.5}]},
        "sim_time": 1800, "replications": 10,
    }).json()
    assert sim["bottleneck_zone_id"] == "B"
    assert sim["scenario"]["throughput_per_hour"]["mean"] > sim["baseline"]["throughput_per_hour"]["mean"]
    assert sim["explanation"]
