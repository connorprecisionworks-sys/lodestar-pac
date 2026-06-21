// Mining prospectivity + economics. Fuses everything the engine knows into a
// single ranked "is this worth mining" signal, and a rough cost/return layer.

const G0 = 9.80665, ISP_CHEM = 320;
const C_BASE = 5e8; // notional baseline mission cost (USD) at near-zero delta-v

// How much we trust the composition, by provenance. Uncertain objects are
// discounted: you do not send a mining mission to something you can't characterize.
function confidenceFactor(r) {
  if (r.type_source === "measured") return 1.0;
  if (r.type_source === "ml-predicted") return Math.max(r.ml_confidence || 0.5, 0.4);
  return 0.45; // assumed
}

// Prospectivity 0..100: geometric mean of normalized value and accessibility,
// discounted by composition confidence.
export function prospectivity(r, meta) {
  if (!meta || r.value_usd == null || r.dv_kms == null) return 0;
  const [lvmin, lvmax] = meta.value_log_range;
  const [dmin, dmax] = meta.dv_range;
  const vn = r.value_usd > 0 ? (Math.log10(r.value_usd) - lvmin) / (lvmax - lvmin) : 0;
  const an = 1 - (r.dv_kms - dmin) / (dmax - dmin);
  const base = Math.sqrt(Math.max(vn, 0) * Math.max(an, 0));
  return Math.round(Math.min(Math.max(base * confidenceFactor(r), 0), 1) * 100);
}

// Rough mission cost (USD): scales with the rocket-equation mass ratio for a
// chemical stage, so harder targets cost dramatically more. Order-of-magnitude.
export function missionCost(dvKms) {
  if (dvKms == null) return null;
  const ratio = Math.exp((dvKms * 1000) / (ISP_CHEM * G0));
  return C_BASE * ratio;
}

// Comparative value-to-cost ratio (higher = more resource value per mission dollar).
export function valueToCost(r) {
  const c = missionCost(r.dv_kms);
  if (!c || r.value_usd == null) return null;
  return r.value_usd / c;
}
