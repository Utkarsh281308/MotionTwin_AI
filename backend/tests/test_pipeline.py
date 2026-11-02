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
    assert sim["bottleneck"]["zone_id"] == "B"
    assert abs(sim["calibration"]["error_pct"]) < 0.25  # model reproduces the video
    assert sim["scenario_changes"] == ["'Pack station' speed x1.5"]
    assert sim["scenario"]["throughput_per_hour"]["mean"] > sim["baseline"]["throughput_per_hour"]["mean"]
    assert sim["explanation"]


def test_demo_quality_report():
    session = client.post("/api/demo/load").json()
    r = client.post(f"/api/sessions/{session['id']}/model").json()
    assert r["summary"]["objects_completed"] == 12
    assert all(s["stopped_share"] > 0.8 for s in r["stations"])  # objects really stop at both stations
    assert not [n for n in r["notices"] if n["level"] == "error"]


def test_transit_zone_and_short_clip_are_flagged():
    session = client.post("/api/demo/load").json()
    # a zone on the walkway between the stations: boxes pass through without stopping
    zones = session["zones"] + [{"id": "W", "name": "Walkway", "capacity": 1, "order": 2, "polygon": [
        {"x": 250, "y": 150}, {"x": 270, "y": 150}, {"x": 270, "y": 210}, {"x": 250, "y": 210}]}]
    client.put(f"/api/sessions/{session['id']}/zones", json=zones)
    r = client.post(f"/api/sessions/{session['id']}/model").json()
    assert any("Walkway" in n["message"] and "transit" in n["message"] for n in r["notices"])


def test_travel_time_excludes_most_queueing():
    session = client.post("/api/demo/load").json()
    model = client.post(f"/api/sessions/{session['id']}/model").json()["model"]
    travel = model["transfer_times"][0]
    assert sum(travel) / len(travel) < 5  # raw exit->entry gaps average ~10 s because of the queue
