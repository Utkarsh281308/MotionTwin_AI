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
| Meta API client (OpenAI-compatible, `https://api.meta.ai/v1`) | `backend/app/meta_client.py` |
| SAM 3.1 segmentation + tracking | `backend/app/vision/meta_sam.py` |
| Masks → centroid tracks | `backend/app/vision/tracker.py` |
| Tracks + zones → enter/exit events | `backend/app/vision/zone_events.py` |
| Events → ProcessModel (arrivals, station times, travel between stations) | `backend/app/simulation/model_builder.py` |
| Data quality: visit counts, stop detection (station vs transit), warnings | `backend/app/simulation/data_quality.py` |
| H.264 playback copies + single frames (bundled ffmpeg via `imageio-ffmpeg`) | `backend/app/vision/video_io.py` |
| SimPy discrete-event simulation | `backend/app/simulation/engine.py` |
| Muse Spark explanation | `backend/app/ai/muse.py` (template fallback if API fails) |
| Data models (single source of truth) | `backend/app/schemas/models.py` ↔ `frontend/src/types.ts` |
| Dashboard UI | `frontend/src/pages/Dashboard.tsx`; `components/`: VideoWorkspace (video + overlay, draw zones), ZoneList, ProcessGraph, EventTimeline, ScenarioPanel (presets A/B/C), ResultsView, Notices |
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
7. Don't invent SAM 3.1 / Muse Spark API details. Implement from Meta's official docs (https://dev.meta.ai/docs).
8. Secrets live in `backend/.env` (`META_API_KEY=...`, git-ignored, loaded in `app/__init__.py`).
   Tests force the key empty (`tests/conftest.py`) so they never call the paid API.
9. Run everything inside **WSL**: `.venv` and `node_modules` were installed from Linux.
10. **Never show a number without its evidence.** Results show the calibration check (model vs video in the
    same window), 95% ranges that include data uncertainty, and data-quality notices. A station is only
    called a bottleneck if busy ≥85% or has a queue ≥1. Otherwise "no bottleneck".
11. Charts follow the dataviz reference palette (baseline = blue slot 1, scenario = orange slot 2,
    observed = grey); status colours only with icon + label; dark mode via CSS variables in `styles.css`.

## How to run
```bash
# backend (from backend/)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/make_demo_data.py      # regenerate demo data (optional)
.venv/bin/python -m pytest -q                   # run tests
.venv/bin/python scripts/check_meta.py          # live check of the Meta key (Muse Spark)
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
- [x] `.env` key loading + `scripts/check_meta.py` live check
- [x] Muse Spark call (`muse-spark-1.3`, Responses API), **live-tested 2026-11-01** ✅. The prompt sends rounded, labelled numbers
- [x] SAM 3.1 **frames mode** (default): sample 10 frames/s → each frame as base64 JPEG `input_image`
      → box centres → linked by `tracker.greedy_track` (shortest-distance-first matching).
      **Live-tested on demo video: 21/21 boxes, 100% detected, 0.7px error, station times +2% / +0%,
      12/12 completed.** ≈ $1.50 per 60s video (600 images × $2.50/1000), ~75s with 8 parallel requests.
- [x] SAM video mode kept for comparison (`request_sam_video`): max 16 objects, re-uses ids → loses visits
- [x] Synthetic 2-station demo (21 parcels, pack station is the bottleneck) + ground truth + MP4 video
      (`make_demo_data.py --video` → `sample_data/videos/demo_parcel_line.mp4`). Queues line up and slide
      forward smoothly, with no box overlap (the earlier version teleported boxes, which broke tracking)
- [x] `scripts/run_sam_demo.py`: live SAM test scored vs ground truth. `--mode frames|video`, `--prompt`,
      `--reuse` re-analyses saved output (`sample_data/ground_truth/demo_sam_raw_<mode>.json`) for free
- [x] **Workspace UI (2026-11-02, after external review):** video plays with live track markers + trails;
      draw/move/resize station boxes on the video; "Test on this frame" prompt preview (1 SAM image);
      inferred-process graph with stat tiles; clickable visit timeline synced to the video; presets
      A (as observed) / B (demand +50%) / C (+1 capacity at most-loaded station) + custom; results =
      calibration card, throughput bars with 95% whiskers, bottleneck verdicts, station meters, Muse text.
      Checked with Playwright screenshots in light + dark mode (no console errors).
- [x] P0 correctness: data-quality notices (short clip, <10 visits, objects never stop = transit zone,
      split ids); per-replication bootstrap so ranges reflect few observations; calibration (simulate the
      clip window from empty, compare completions); evidence-based bottleneck (ties → longest queue);
      travel time between stations (fastest 25% of exit→entry gaps, so queue time isn't double counted).
      Demo: calibration +7% ("matches the video").
- [x] Uploads get an H.264 faststart copy for the browser; demo video regenerated as H.264
- [x] "Load demo" replays the recorded live SAM 3.1 run (cached parse; Meta's parser is ~30 ms/frame)
- [x] Tests: zone events, SAM parser, tracker, engine, bottleneck rules, data quality, calibration, travel time (17 passing; `pytest.ini` limits to `tests/`)
- [x] Dashboard: load demo, upload video, zone editor (numeric rectangles over track paths),
      scenario panel (capacity, speed, arrival rate), results (throughput bars, station table, explanation)

###  To do (MVP, in priority order)
- [x] Valid key in `backend/.env`
- [ ] **Test on a real 30–60 s video with real stopping points** (first stock clip was a 5 s CGI conveyor
      loop with no stations, so it is unusable). Use "Test on this frame" to pick the prompt first
- [ ] Travel time is overestimated when a station is saturated the whole clip (every object queued);
      demo: 3.7 s measured vs ~1.5 s true. Could detect "moving" vs "waiting" from track speed instead
- [ ] Demo script for judges: Load demo → play video → build model → A, B (output doesn't rise: Pack is
      the constraint), C (+1 at Pack → throughput up, queue gone) → point at calibration
- [ ] Arrivals are measured when objects ENTER the first station, so a queue before it hides the true
      arrival rate (demo: 3.21s measured vs 2.96s true gap). Add an optional "entry line" zone for arrivals
- [ ] Tracking runs synchronously in the request (~75s for 60s video); move to a background job + progress
- [ ] Record 1–3 real sample videos → `sample_data/videos/` + hand-labelled ground truth timings
- [ ] Validation report: simulated vs observed throughput/service times on real videos
- [ ] Polygon zones (currently rectangles drawn on the video)
- [ ] Muse Spark: suggest zones automatically from the first frame (user still confirms)
- [ ] Warm-up period in simulation (observed throughput is lower than steady state on a short video)
- [ ] Handle parallel/branching flows (currently serial line only)
- [ ] Charts (queue length over time), assumptions panel in UI
- [ ] Demo video + hackathon submission write-up

###  Out of scope
3D digital twins, robot control, automatic reconstruction of arbitrary factories.

## Decisions log
- 2026-10-31: Initial scaffold. Sessions stored in memory (fine for hackathon). Service-time
  distributions are empirical (resample observed values) rather than fitted. Simple, honest,
  testable. Utilisation/queue measured by sampling every 1s of sim time.
- 2026-11-01: Meta API is OpenAI-compatible, so we use the `openai` SDK with base_url. SAM: use box
  centres, not masks (positions are all we need; masks are expensive to decode). Videos must be
  MP4/MOV (H.264/H.265), at most 15,000 frames, billed per frame (min 50). Concept prompt = ONE short
  noun phrase per request.
- 2026-11-01: Pytest must never call the paid API: `pytest.ini` testpaths=tests, and paid scripts are
  NOT named `test_*`.
- 2026-11-01: SAM experiments on the demo video (prompt "cardboard box" → 3/21 boxes in video mode).
  Prompt wording matters: per frame, "brown box" found all, "parcel" none, "package" some, "box" also
  matched station mats. Video mode with "brown box": 16 tracks (the 16-object cap), 86% detections,
  completed 5/12. Switched to frames mode → near-perfect. Base64 data URLs work for `input_image`.
  Prices: SAM $0.20/1000 video frames, $2.50/1000 images; Muse Spark $1.25/$4.25 per M tokens in/out.
- 2026-11-02: External review (6.5/10: "engineering prototype"; wants credibility + video-backed model).
  Responded with P0 correctness + P1 workspace UI above. Zone time ≠ service time unless objects stop:
  we now measure stopping and warn. Muse prompt receives verdicts + calibration + warnings, and is told
  to say "no bottleneck" / "provisional" accordingly. Deadline: 4 November.
