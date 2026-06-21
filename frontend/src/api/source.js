// Static data source: loads the exported JSON once and serves the same shapes
// the FastAPI backend does (meta / asteroids / detail / trajectory), with
// ranking + screening trajectory computed client-side. This is what lets the
// app deploy to Vercel with no backend. Swap to ./client.js for a live API.

import { accessNorm, composite, rendezvousBreakdown, valueNorm } from "../lib/compute.js";

let _cache = null;

async function load() {
  if (_cache) return _cache;
  const res = await fetch("/data/asteroids.json");
  if (!res.ok) throw new Error(`failed to load dataset (${res.status})`);
  const data = await res.json();
  const f = data.fields;
  const idx = Object.fromEntries(f.map((name, i) => [name, i]));
  const records = data.rows.map((r) => {
    const o = {};
    for (const name of f) o[name] = r[idx[name]];
    o.dv_source = r[idx.dv_source] === "benner" ? "asterank-benner" : "computed:hohmann-proxy";
    o.spec_is_assumed = !!r[idx.spec_is_assumed];
    o.spec_type = r[idx.spec_type] || null;
    return o;
  });
  const byId = new Map(records.map((r) => [r.id, r]));
  _cache = { records, byId, meta: data.meta };
  return _cache;
}

export const source = {
  async meta() {
    return (await load()).meta;
  },

  async asteroids({ weight = 0.5, spec = "all", dv_max, q = "", sort = "score", page = 0, page_size = 50 }) {
    const { records, meta } = await load();
    const [lo, hi] = meta.value_log_range;
    const [dlo, dhi] = meta.dv_range;
    const ql = q.trim().toLowerCase();

    let view = records.filter((r) => {
      if (dv_max != null && r.dv_kms > dv_max) return false;
      if (spec === "measured" && r.spec_is_assumed) return false;
      if ((spec === "C" || spec === "S" || spec === "M") && r.value_complex !== spec) return false;
      if (ql && !r.full_name.toLowerCase().includes(ql)) return false;
      return true;
    });
    for (const r of view) {
      r.score = composite(valueNorm(r.value_usd, lo, hi), accessNorm(r.dv_kms, dlo, dhi), weight);
    }
    const asc = sort === "dv_kms" || sort === "full_name";
    view.sort((a, b) => {
      const av = a[sort], bv = b[sort];
      if (typeof av === "string") return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      return asc ? (av || 0) - (bv || 0) : (bv || 0) - (av || 0);
    });
    const total = view.length;
    const items = view.slice(page * page_size, page * page_size + page_size);
    return { total, page, page_size, items };
  },

  async detail(id) {
    const { byId } = await load();
    return byId.get(id) || null;
  },

  async trajectory(id) {
    const { byId } = await load();
    const r = byId.get(id);
    if (!r) throw new Error("not found");
    const bd = rendezvousBreakdown(r.a_au, r.e, r.i_deg);
    return {
      id,
      full_name: r.full_name,
      dv_headline_kms: r.dv_kms,
      dv_source: r.dv_source,
      breakdown: bd,
      phase2_note: "Schematic transfer only. Real launch windows (porkchop) and "
        + "optimized transfer arcs arrive in Phase 2.",
    };
  },
};
