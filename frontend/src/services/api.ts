import type { Comparison, ProcessModel, Scenario, Session, Zone, ZoneEvent } from "../types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: init?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  loadDemo: () => request<Session>("/demo/load", { method: "POST" }),
  uploadVideo: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Session>("/videos", { method: "POST", body: form });
  },
  track: (id: string, prompt: string) =>
    request<Session>(`/sessions/${id}/track?prompt=${encodeURIComponent(prompt)}`, { method: "POST" }),
  setZones: (id: string, zones: Zone[]) =>
    request<Session>(`/sessions/${id}/zones`, { method: "PUT", body: JSON.stringify(zones) }),
  buildModel: (id: string) =>
    request<{ events: ZoneEvent[]; model: ProcessModel }>(`/sessions/${id}/model`, { method: "POST" }),
  simulate: (model: ProcessModel, scenario: Scenario | null) =>
    request<Comparison>("/simulate", { method: "POST", body: JSON.stringify({ model, scenario }) }),
};
