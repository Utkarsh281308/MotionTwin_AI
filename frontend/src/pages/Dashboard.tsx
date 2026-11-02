import { useEffect, useRef, useState } from "react";
import EventTimeline from "../components/EventTimeline";
import Notices from "../components/Notices";
import ProcessGraph from "../components/ProcessGraph";
import ResultsView from "../components/ResultsView";
import ScenarioPanel from "../components/ScenarioPanel";
import VideoWorkspace from "../components/VideoWorkspace";
import ZoneList from "../components/ZoneList";
import { secs } from "../lib/format";
import { api } from "../services/api";
import type { Comparison, ModelResponse, PreviewBox, Scenario, Session, Zone } from "../types";

const AS_OBSERVED: Scenario = { name: "As observed", station_changes: [], arrival_rate_factor: 1 };

export default function Dashboard() {
  const [session, setSession] = useState<Session | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [selectedZone, setSelectedZone] = useState<string | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [prompt, setPrompt] = useState("brown box");
  const [preview, setPreview] = useState<{ boxes: PreviewBox[]; frame: number } | null>(null);
  const [model, setModel] = useState<ModelResponse | null>(null);
  const [modelStale, setModelStale] = useState(false);
  const [scenario, setScenario] = useState<Scenario>(AS_OBSERVED);
  const [result, setResult] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [time, setTime] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Follow the video smoothly (timeupdate only fires ~4x per second).
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const v = videoRef.current;
      if (v) setTime(v.currentTime);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  const run = async (message: string, fn: () => Promise<void>) => {
    setError(null);
    setBusy(message);
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };

  const start = (s: Session) => {
    setSession(s); setZones(s.zones); setModel(null); setResult(null); setPreview(null);
    setScenario(AS_OBSERVED); setSelectedZone(null); setModelStale(false);
  };

  const changeZones = (z: Zone[]) => {
    setZones(z);
    if (model) setModelStale(true);
  };

  const seek = (t: number) => {
    if (videoRef.current) { videoRef.current.currentTime = t; videoRef.current.pause(); }
  };

  const loadDemo = () => run("Loading demo…", async () => start(await api.loadDemo()));
  const upload = (file: File) => run("Uploading and preparing video…", async () => start(await api.uploadVideo(file)));
  const testPrompt = () => run("Asking SAM 3.1 about this frame…", async () => {
    const frame = Math.round(time * session!.fps);
    const p = await api.preview(session!.id, prompt, frame);
    setPreview({ boxes: p.boxes, frame });
  });
  const track = () => run("Tracking objects with SAM 3.1 (about a minute for a 60 s clip)…", async () => {
    const s = await api.track(session!.id, prompt);
    setSession(s); setPreview(null); setModel(null); setResult(null);
  });
  const buildModel = () => run("Building process model…", async () => {
    await api.setZones(session!.id, zones);
    setModel(await api.buildModel(session!.id));
    setModelStale(false);
    setResult(null);
  });
  const simulate = (s: Scenario) => run("Simulating…", async () => {
    setResult(await api.simulate(model!.model, s, model!.notices));
  });

  const hasTracks = !!session?.tracks.length;

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>MotionTwin AI</h1>
          <p className="subtitle">Video-to-simulation workspace</p>
        </div>
        <div className="topbar-actions">
          <button className="secondary" onClick={loadDemo} disabled={!!busy}>Load demo parcel line</button>
          <label className={`button ${busy ? "disabled" : ""}`}>
            Upload video
            <input type="file" accept="video/mp4,video/quicktime" hidden disabled={!!busy}
              onChange={(e) => { if (e.target.files?.[0]) upload(e.target.files[0]); e.target.value = ""; }} />
          </label>
        </div>
      </header>

      {busy && <div className="banner busy" role="status">{busy}</div>}
      {error && <div className="banner error" role="alert">⛔ {error}</div>}

      {!session && (
        <section className="card empty">
          <h2>Turn a video of a physical process into a simulation you can experiment with</h2>
          <ol>
            <li>Load the demo, or upload a 30–60 s clip from a fixed camera.</li>
            <li>Track objects with SAM 3.1 and mark the work stations on the video.</li>
            <li>MotionTwin measures arrivals and station times, checks the model against the video, and lets you test changes.</li>
          </ol>
        </section>
      )}

      {session && (
        <>
          <div className="workspace">
            <section className="card video-card">
              <div className="card-head">
                <h2>Source video</h2>
                <span className="muted small">
                  {secs(session.duration)} · {Math.round(session.fps)} fps · {session.width}×{session.height}
                  {session.track_source && <> · tracks: {session.track_source}</>}
                </span>
              </div>
              <VideoWorkspace session={session} videoUrl={session.playback_path ? api.videoUrl(session.id) : null}
                videoRef={videoRef} time={time} zones={zones} onZonesChange={changeZones}
                selectedZoneId={selectedZone} onSelectZone={setSelectedZone}
                drawing={drawing} onDrawingDone={() => setDrawing(false)}
                previewBoxes={preview && Math.abs(preview.frame - time * session.fps) < 2 ? preview.boxes : []} />

              <div className="track-controls">
                <label className="inline">
                  Objects to track
                  <input value={prompt} onChange={(e) => setPrompt(e.target.value)} disabled={!!busy} />
                </label>
                <button className="secondary" onClick={testPrompt} disabled={!!busy || !session.video_path}
                  title="Runs SAM on the current frame only (≈ $0.0025)">Test on this frame</button>
                <button onClick={track} disabled={!!busy || !session.video_path}
                  title="Runs SAM on 10 frames per second (≈ $1.50 per minute of video)">
                  {hasTracks ? "Re-track video" : "Track objects"}
                </button>
                {preview && (
                  <span className="muted small">
                    Found <b>{preview.boxes.length}</b> “{prompt}” on frame {preview.frame} (dashed boxes).
                  </span>
                )}
              </div>
              <p className="muted small">
                Use a short, specific description. On the demo, “brown box” found every box and “parcel” found none.
              </p>
            </section>

            <section className="card stations-card">
              <div className="card-head">
                <h2>Stations</h2>
                <button className={drawing ? "" : "secondary"} onClick={() => setDrawing(!drawing)} disabled={!!busy}>
                  {drawing ? "Drag on the video…" : "+ Draw station"}
                </button>
              </div>
              <p className="muted small">
                Draw a box over each spot where objects <b>stop to be worked on</b>, not over conveyors or queues.
                Drag a box to move it; drag its corner to resize.
              </p>
              <ZoneList zones={zones} onChange={changeZones} selectedZoneId={selectedZone} onSelect={setSelectedZone} />
              <button onClick={buildModel} disabled={!!busy || !zones.length || !hasTracks}
                title={!hasTracks ? "Track objects first" : undefined}>
                {model ? "Rebuild process model" : "Build process model"}
              </button>
              {modelStale && <p className="warn-text small">⚠ Stations changed. Rebuild the model to update.</p>}
            </section>
          </div>

          {model && (
            <section className="card">
              <div className="card-head">
                <h2>Inferred process</h2>
                <span className="muted small">measured from the video · hover for definitions</span>
              </div>
              <ProcessGraph result={model} stale={modelStale} />
              <h3>Station visits over time</h3>
              <EventTimeline events={model.events} zones={zones.length ? [...zones].sort((a, b) => a.order - b.order) : []}
                duration={session.duration} time={time} onSeek={seek} />
              <Notices notices={model.notices} />
            </section>
          )}

          {model && !modelStale && (
            <section className="card">
              <div className="card-head">
                <h2>What-if scenarios</h2>
                <span className="muted small">each run: 30 simulated hours with resampled observations</span>
              </div>
              <ScenarioPanel model={model.model} scenario={scenario} onChange={setScenario} onRun={simulate} busy={!!busy} />
            </section>
          )}

          {result && model && !modelStale && <ResultsView result={result} />}
        </>
      )}
    </div>
  );
}
