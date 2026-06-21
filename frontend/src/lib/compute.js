// Client-side port of the backend ranking (score.py) and screening trajectory
// (deltav.rendezvous_breakdown). Keeps the static deploy backend-free while
// staying numerically identical to the server.

const V_EARTH = 29.784, V_LEO = 7.726;
export const PROXY_REL_UNC = 0.35;

export function valueNorm(v, lo, hi) {
  if (!(v > 0) || hi <= lo) return 0;
  return Math.min(Math.max((Math.log10(v) - lo) / (hi - lo), 0), 1);
}
export function accessNorm(dv, lo, hi) {
  if (dv == null || hi <= lo) return 0;
  return Math.min(Math.max(1 - (dv - lo) / (hi - lo), 0), 1);
}
export function composite(vn, an, w) {
  w = Math.min(Math.max(w, 0), 1);
  return Math.pow(Math.max(vn, 1e-4), w) * Math.pow(Math.max(an, 1e-4), 1 - w);
}

const visViva = (r, a) => V_EARTH * Math.sqrt(Math.max(2 / r - 1 / a, 0));

export function rendezvousBreakdown(a, e, iDeg) {
  if (a == null || e == null || iDeg == null) return null;
  if (a <= 0 || e < 0 || e >= 1) return null;
  const i = (iDeg * Math.PI) / 180;
  const r1 = 1.0;
  const r2 = a >= 1 ? a * (1 + e) : a * (1 - e);
  if (r2 <= 0) return null;
  const at = (r1 + r2) / 2;
  const vDepCirc = V_EARTH / Math.sqrt(r1);
  const vtDep = visViva(r1, at), vtArr = visViva(r2, at), vAst = visViva(r2, a);
  let vinf, dvArr;
  if (r2 >= r1) {
    vinf = Math.abs(vtDep - vDepCirc);
    dvArr = Math.sqrt(vAst * vAst + vtArr * vtArr - 2 * vAst * vtArr * Math.cos(i));
  } else {
    vinf = Math.sqrt(vDepCirc * vDepCirc + vtDep * vtDep - 2 * vDepCirc * vtDep * Math.cos(i));
    dvArr = Math.abs(vAst - vtArr);
  }
  const dvLaunch = Math.sqrt(vinf * vinf + 2 * V_LEO * V_LEO) - V_LEO;
  return {
    dv_launch_kms: +dvLaunch.toFixed(3),
    dv_arrive_kms: +dvArr.toFixed(3),
    dv_total_kms: +(dvLaunch + dvArr).toFixed(3),
    transfer_target_au: +r2.toFixed(4),
    transfer_sma_au: +at.toFixed(4),
    rel_uncertainty: PROXY_REL_UNC,
    grade: "screening (patched-conic Hohmann); Phase 2 replaces with Lambert/porkchop",
  };
}
