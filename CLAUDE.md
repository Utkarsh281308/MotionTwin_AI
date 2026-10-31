# MotionTwin AI: project memory

> **Keep this file updated.** After every work session, tick off finished items in
> "Status", add new TODOs, and log anything important under "Decisions".

## What it is
Built for the Meta Global AI Developer Hackathon (Indie Developer Track, "Push the Frontier").
Record a short video (30–60s) of a physical workflow (warehouse/manufacturing) → track objects
→ detect zone enter/exit times → build a queueing model → simulate "what-if" changes →
compare baseline vs scenario with uncertainty → AI explains the bottleneck.

## Pipeline (and where the code lives)
| Step | File |
|---|---|
| Upload video / sessions / API | `backend/app/api/routes.py` |
| SAM 3.1 segmentation + tracking | `backend/app/vision/meta_sam.py` (**stub**) |
| Masks → centroid tracks | `backend/app/vision/tracker.py` |
| Tracks + zones → enter/exit events | `backend/app/vision/zone_events.py` |
| Events → ProcessModel | `backend/app/simulation/model_builder.py` |
| SimPy discrete-event simulation | `backend/app/simulation/engine.py` |
| Muse Spark explanation | `backend/app/ai/muse.py` (**stub + template fallback**) |
| Data models (single source of truth) | `backend/app/schemas/models.py` ↔ `frontend/src/types.ts` |
| Dashboard UI | `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/*` |
| Synthetic demo data | `backend/scripts/make_demo_data.py` → `sample_data/ground_truth/` |

## Rules (do not break)
1. **Muse Spark never calculates numbers.** All throughput/queue/utilisation numbers come from
   the deterministic simulation; Muse only explains them.
2. **Simulation is reproducible:** same seed gives the same result. Baseline and scenario share seeds.
3. **Users can always correct zones** before building the model (one wrong zone breaks everything).
4. Zones cover the **work spot, not the queue**. Time in zone = service time.
5. Visits that are cut off (object already inside at track start, or still inside at track end) are
   marked `censored` and excluded from service times.
6. If you change `schemas/models.py`, update `frontend/src/types.ts` too.
7. Don't invent SAM 3.1 / Muse Spark API details. Implement from Meta's official docs.

## How to run
```bash
# backend (from backend/)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/make_demo_data.py      # regenerate demo data (optional)
.venv/bin/python -m pytest -q                   # run tests
.venv/bin/uvicorn app.main:app --reload         # http://localhost:8000/docs

# frontend (from frontend/)
npm install && npm run dev                      # http://localhost:5173 (proxies /api → :8000)
```

## Status

###  Done
- [x] Project structure (backend FastAPI + frontend React/TS/Vite)
- [x] Pydantic schemas for the full pipeline
- [x] Zone event extraction (point-in-polygon, min-frame noise filter, censoring)
- [x] Mask → centroid tracks + greedy fallback tracker
- [x] Process model builder (interarrival times, per-station service times, observed throughput)
- [x] SimPy engine: serial stations, capacity, speed factor, arrival-rate factor, N replications, 95% CI
- [x] Bottleneck detection (highest utilisation)
- [x] API: health, upload, track (501 until SAM is done), demo load, set zones, build model, simulate
- [x] Template explanation fallback (works with no API key)
- [x] Synthetic 2-station demo (20 parcels, pack station is the bottleneck) + ground truth
- [x] Tests: zone events, engine determinism/behaviour, end-to-end demo vs ground truth (7 passing)
- [x] Dashboard: load demo, upload video, zone editor (numeric rectangles over track paths),
      scenario panel (capacity, speed, arrival rate), results (throughput bars, station table, explanation)

###  To do (MVP, in priority order)
- [ ] **SAM 3.1 integration** in `meta_sam.py` (get API access, return `{frame: {obj_id: mask}}`, read fps with OpenCV)
- [ ] **Muse Spark integration** in `muse.py` `_call_muse_spark()` (prompt already built in `build_prompt`)
- [ ] Record 1–3 real sample videos → `sample_data/videos/` + hand-labelled ground truth timings
- [ ] Validation report: simulated vs observed throughput/service times on real videos
- [ ] Show the first video frame behind the zone editor (currently only track paths on dark background)
- [ ] Drag-to-draw / polygon zones in the UI (currently numeric rectangles)
- [ ] Muse Spark: suggest zones automatically from the first frame (user still confirms)
- [ ] Warm-up period in simulation (observed throughput is lower than steady state on a short video)
- [ ] Handle parallel/branching flows (currently serial line only)
- [ ] Run processing as background jobs (SAM on a 60s video will be slow) + progress in UI
- [ ] Charts (queue length over time), assumptions panel in UI
- [ ] Demo video + hackathon submission write-up

###  Out of scope
3D digital twins, robot control, automatic reconstruction of arbitrary factories.

## Decisions log
- 2026-10-31: Initial scaffold. Sessions stored in memory (fine for hackathon). Service-time
  distributions are empirical (resample observed values) rather than fitted. Simple, honest,
  testable. Utilisation/queue measured by sampling every 1s of sim time.
