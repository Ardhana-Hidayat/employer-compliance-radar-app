const BASE = "http://127.0.0.1:8000";

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  health: () => get("/api/health"),
  sektorList: () => get("/api/sektor"),
  employers: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== "")
    ).toString();
    return get(`/api/employers${qs ? `?${qs}` : ""}`);
  },
  metrics: () => get("/api/metrics"),
  rescoring: (weights) => post("/api/rescoring", weights),
};
