// Static data source: loads the exported JSON once and serves the same shapes
// the FastAPI backend does (meta / asteroids / detail / trajectory), with
// ranking + screening trajectory computed client-side. This is what lets the
// app deploy to Vercel with no backend. Swap to ./client.js for a live API.

import { accessNorm, composite, rendezvousBreakdown, valueNorm } from "../lib/compute.js";
import { porkchop, todayJd, transferPath } from "../lib/astro.js";

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
    const { records, meta } = await load();
    const predicted = records.filter((r) => r.type_source === "ml-predicted").length;
    return { ...meta, predicted_types: predicted };
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

    const hasEpoch = r.epoch_jd != null && r.a_au != null && r.ma_deg != null && r.i_deg != null;
    if (hasEpoch) {
      const el = { a: r.a_au, e: r.e, i: r.i_deg, om: r.om_deg, w: r.w_deg, ma: r.ma_deg, epoch: r.epoch_jd };
      const start = todayJd();
      const pc = porkchop(el, start);
      const path = pc.optimal
        ? transferPath(el, start + pc.optimal.depOffsetDays, pc.optimal.tofDays)
        : null;
      return {
        id, mode: "porkchop", full_name: r.full_name,
        dv_headline_kms: r.dv_kms, dv_source: r.dv_source,
        startJd: start, depOffsets: pc.depOffsets, tofs: pc.tofs, grid: pc.grid,
        optimal: pc.optimal, transferPath: path,
        phase2_note: "Real two-body Lambert porkchop. Horizons-precision ephemerides are a later upgrade.",
      };
    }

    return {
      id, mode: "screening", full_name: r.full_name,
      dv_headline_kms: r.dv_kms, dv_source: r.dv_source,
      breakdown: rendezvousBreakdown(r.a_au, r.e, r.i_deg),
      phase2_note: "Schematic transfer. Re-run the data pipeline to capture orbital "
        + "epochs and unlock real launch-window porkchops.",
    };
  },
};
