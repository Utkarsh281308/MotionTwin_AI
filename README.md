# MotionTwin AI

**Turn real-world videos into interactive digital simulations.**

Record a physical process. MotionTwin tracks how objects move through it, reconstructs a
simplified process model, and lets you test operational changes (more capacity, faster
stations, more arrivals) before making them in the real world.

Built for the Meta Global AI Developer Hackathon (Indie Developer Track).

## How it works
1. **Upload** a 30–60s video of a small workflow
2. **Track** objects with SAM 3.1 (segmentation + tracking)
3. **Define/correct zones** for each processing station
4. **Extract** arrival and enter/exit timestamps per station
5. **Simulate** with a SimPy discrete-event model (30 replications, 95% confidence intervals)
6. **Compare** baseline vs scenario; Muse Spark explains the bottleneck (numbers come from the simulation only)

## Stack
React + TypeScript (Vite) · Python + FastAPI · SAM 3.1 · Muse Spark · OpenCV + NumPy · SimPy

## Quick start
```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload

cd ../frontend
npm install 
npm run dev
```
Open http://localhost:5173 and click **Load demo parcel line**.

Tests: `cd backend && .venv/bin/python -m pytest -q`
