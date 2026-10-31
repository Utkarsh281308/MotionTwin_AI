import { useState } from "react";
import ResultsView from "../components/ResultsView";
import ScenarioPanel from "../components/ScenarioPanel";
import ZoneEditor from "../components/ZoneEditor";
import { api } from "../services/api";
import type { Comparison, ProcessModel, Scenario, Session, Zone } from "../types";

const emptyScenario: Scenario = { name: "scenario", station_changes: [], arrival_rate_factor: 1 };

export default function Dashboard() {
  const [session, setSession] = useState<Session | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [model, setModel] = useState<ProcessModel | null>(null);
  const [scenario, setScenario] = useState<Scenario>(emptyScenario);
  const [result, setResult] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (fn: () => Promise<void>) => {
    setError(null);
    setBusy(true);
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  const start = (s: Session) => {
    setSession(s); setZones(s.zones); setModel(null); setResult(null); setScenario(emptyScenario);
  };

  const loadDemo = () => run(async () => start(await api.loadDemo()));

  const upload = (file: File) => run(async () => {
    const s = await api.uploadVideo(file);
    start(await api.track(s.id, "parcel"));
  });

  const buildModel = () => run(async () => {
    await api.setZones(session!.id, zones);
    setModel((await api.buildModel(session!.id)).model);
    setResult(null);
  });

  const simulate = () => run(async () => setResult(await api.simulate(model!, scenario)));

  return (
    <main>
      <h1>MotionTwin AI</h1>
      <p className="subtitle">Turn real-world videos into interactive process simulations</p>
      {error && <p className="error">{error}</p>}

      <section>
        <h2>1. Video</h2>
        <button onClick={loadDemo} disabled={busy}>Load demo parcel line</button>{" "}
        <input type="file" accept="video/*" disabled={busy}
          onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        {session && <p>{session.tracks.length} tracked objects · {session.duration}s @ {session.fps} fps</p>}
      </section>

      {session && (
        <section>
          <h2>2. Process zones <small>(check and correct the stations)</small></h2>
          <ZoneEditor session={session} zones={zones} onChange={setZones} />
          <button onClick={buildModel} disabled={busy || zones.length === 0}>Build process model</button>
        </section>
      )}

      {model && (
        <section>
          <h2>3. Scenario</h2>
          <ScenarioPanel model={model} scenario={scenario} onChange={setScenario} />
          <button onClick={simulate} disabled={busy}>{busy ? "Simulating…" : "Run simulation"}</button>
        </section>
      )}

      {result && (
        <section>
          <h2>4. Baseline vs scenario</h2>
          <ResultsView result={result} />
        </section>
      )}
    </main>
  );
}
