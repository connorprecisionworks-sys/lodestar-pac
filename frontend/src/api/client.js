// Thin client for the Lodestar FastAPI backend. Dev server proxies /api -> :8000.

async function get(path, params) {
  const url = new URL(path, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    }
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  meta: () => get("/api/meta"),
  asteroids: (params) => get("/api/asteroids", params),
  detail: (id) => get(`/api/asteroids/${id}`),
  trajectory: (id) => get(`/api/trajectory/${id}`),
};
