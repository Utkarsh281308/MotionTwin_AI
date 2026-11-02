"""Live check of the Meta API key: asks Muse Spark to explain the demo simulation.

Usage (from backend/):  .venv/bin/python scripts/check_meta.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.ai import muse  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
session = client.post("/api/demo/load").json()
model = client.post(f"/api/sessions/{session['id']}/model").json()["model"]

from app.schemas.models import ProcessModel, Scenario, StationChange  # noqa: E402
from app.simulation.engine import find_bottleneck, simulate  # noqa: E402

pm = ProcessModel(**model)
base = simulate(pm, replications=10)
scen = simulate(pm, Scenario(name="faster packing", station_changes=[StationChange(zone_id="B", speed_factor=1.5)]),
                replications=10)
print("Calling Muse Spark...")
try:
    print("\n" + muse._call_muse_spark(muse.build_prompt(pm.observed_completed / pm.observed_duration * 3600, base, scen)))
    print("\n✅ Meta API key works")
except Exception as e:
    print(f"\n❌ Muse Spark call failed: {e}")
    print("(bottleneck from simulation:", find_bottleneck(base), ")")
