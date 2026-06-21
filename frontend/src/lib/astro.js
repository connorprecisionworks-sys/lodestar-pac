// Phase 2 astrodynamics, ported from the validated Python engine (kepler.py,
// lambert.py, porkchop.py). Runs in-browser so the static deploy computes real
// launch windows on demand. Numerically identical to the backend reference.
// Units: AU, days. mu_sun in AU^3/day^2.

export const MU_SUN = 0.01720209895 ** 2;
export const AU_DAY_TO_KMS = 1731.456837;
const V_LEO = 7.726;

export const EARTH_J2000 = {
  a: 1.00000011, e: 0.01671022, i: 0.0, om: 0.0, w: 102.93768193,
  ma: 100.46435 - 102.93768193, epoch: 2451545.0, period: 365.256363,
};

const D2R = Math.PI / 180;

// --- small vector helpers ---
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a) => Math.sqrt(dot(a, a));
const scale = (a, s) => [a[0] * s, a[1] * s, a[2] * s];

function solveKepler(M, e) {
  let E = e < 0.8 ? M : Math.PI;
  for (let n = 0; n < 80; n++) {
    const d = (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
    E -= d;
    if (Math.abs(d) < 1e-12) break;
  }
  return E;
}

function rotate(xp, yp, om, i, w) {
  const cO = Math.cos(om), sO = Math.sin(om), ci = Math.cos(i), si = Math.sin(i), cw = Math.cos(w), sw = Math.sin(w);
  return [
    (cO * cw - sO * sw * ci) * xp + (-cO * sw - sO * cw * ci) * yp,
    (sO * cw + cO * sw * ci) * xp + (-sO * sw + cO * cw * ci) * yp,
    (sw * si) * xp + (cw * si) * yp,
  ];
}

export function propagate(el, jd) {
  const a = +el.a, e = +el.e;
  const i = (+el.i) * D2R, om = (+el.om) * D2R, w = (+el.w) * D2R, ma0 = (+el.ma) * D2R;
  const epoch = +el.epoch;
  const n = Math.sqrt(MU_SUN / a ** 3);
  let M = ma0 + n * (jd - epoch);
  M = ((M + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI;
  const E = solveKepler(M, e);
  const cosE = Math.cos(E), sinE = Math.sin(E);
  const xp = a * (cosE - e), yp = a * Math.sqrt(1 - e * e) * sinE;
  const edot = n / (1 - e * cosE);
  const vxp = -a * sinE * edot, vyp = a * Math.sqrt(1 - e * e) * cosE * edot;
  return [rotate(xp, yp, om, i, w), rotate(vxp, vyp, om, i, w)];
}

export const earthState = (jd) => propagate(EARTH_J2000, jd);

// --- Lambert (universal variables, Curtis Alg 5.2) ---
function stumpffC(z) {
  if (z > 1e-9) return (1 - Math.cos(Math.sqrt(z))) / z;
  if (z < -1e-9) return (Math.cosh(Math.sqrt(-z)) - 1) / -z;
  return 0.5;
}
function stumpffS(z) {
  if (z > 1e-9) { const s = Math.sqrt(z); return (s - Math.sin(s)) / s ** 3; }
  if (z < -1e-9) { const s = Math.sqrt(-z); return (Math.sinh(s) - s) / s ** 3; }
  return 1 / 6;
}

export function lambert(r1, r2, dt, mu, prograde = true) {
  const R1 = norm(r1), R2 = norm(r2);
  const cr = cross(r1, r2);
  let cdnu = dot(r1, r2) / (R1 * R2);
  cdnu = Math.max(-1, Math.min(1, cdnu));
  let dnu = Math.acos(cdnu);
  if (prograde) { if (cr[2] < 0) dnu = 2 * Math.PI - dnu; }
  else { if (cr[2] >= 0) dnu = 2 * Math.PI - dnu; }
  if (Math.abs(1 - Math.cos(dnu)) < 1e-12) return null;
  const A = Math.sin(dnu) * Math.sqrt(R1 * R2 / (1 - Math.cos(dnu)));
  if (Math.abs(A) < 1e-12) return null;

  const y = (z) => R1 + R2 + A * (z * stumpffS(z) - 1) / Math.sqrt(stumpffC(z));
  let z = 0, converged = false;
  for (let k = 0; k < 100; k++) {
    if (!Number.isFinite(z) || z > 4 * Math.PI ** 2 || z < -4 * Math.PI ** 2) return null;
    const C = stumpffC(z), S = stumpffS(z), yz = y(z);
    if (A > 0 && yz < 0) { z += 0.1; continue; }
    if (yz <= 0 || C <= 0) return null;
    const chi = Math.sqrt(yz / C);
    const F = chi ** 3 * S + A * Math.sqrt(yz) - Math.sqrt(mu) * dt;
    let dFdz;
    if (Math.abs(z) < 1e-9) {
      dFdz = (Math.SQRT2 / 40) * yz ** 1.5 + (A / 8) * (Math.sqrt(yz) + A * Math.sqrt(1 / (2 * yz)));
    } else {
      dFdz = (yz / C) ** 1.5 * ((1 / (2 * z)) * (C - 1.5 * S / C) + 0.75 * S ** 2 / C)
        + (A / 8) * (3 * (S / C) * Math.sqrt(yz) + A * Math.sqrt(C / yz));
    }
    if (dFdz === 0) return null;
    const dz = F / dFdz;
    z -= dz;
    if (Math.abs(dz) < 1e-8) { converged = true; break; }
  }
  if (!converged || !Number.isFinite(z)) return null;
  const yz = y(z);
  if (yz <= 0) return null;
  const f = 1 - yz / R1, g = A * Math.sqrt(yz / mu), gdot = 1 - yz / R2;
  const v1 = scale(sub(r2, scale(r1, f)), 1 / g);
  const v2 = scale(sub(scale(r2, gdot), r1), 1 / g);
  return [v1, v2];
}

const leoDeparture = (vinf) => Math.sqrt(vinf * vinf + 2 * V_LEO * V_LEO) - V_LEO;

export function transferDv(el, depJd, tof) {
  const [rE, vE] = earthState(depJd);
  const [rA, vA] = propagate(el, depJd + tof);
  const sol = lambert(rE, rA, tof, MU_SUN, true);
  if (!sol) return null;
  const [v1, v2] = sol;
  const vinf = norm(sub(v1, vE)) * AU_DAY_TO_KMS;
  const dvArr = norm(sub(v2, vA)) * AU_DAY_TO_KMS;
  const dvLaunch = leoDeparture(vinf);
  return { dvLaunch, dvArrive: dvArr, dvTotal: dvLaunch + dvArr };
}

export function porkchop(el, startJd, opts = {}) {
  const { depSpan = 730, depStep = 15, tofMin = 70, tofMax = 760, tofStep = 20 } = opts;
  const deps = [], tofs = [];
  for (let d = 0; d <= depSpan; d += depStep) deps.push(d);
  for (let t = tofMin; t <= tofMax; t += tofStep) tofs.push(t);
  const grid = tofs.map(() => deps.map(() => null));
  let best = null;
  deps.forEach((d, ci) => {
    tofs.forEach((t, ri) => {
      const res = transferDv(el, startJd + d, t);
      if (!res || !Number.isFinite(res.dvTotal)) return;
      grid[ri][ci] = res.dvTotal;
      if (!best || res.dvTotal < best.dvTotal) best = { ...res, depOffset: d, tof: t };
    });
  });
  return {
    startJd, depOffsets: deps, tofs, grid,
    optimal: best && {
      depOffsetDays: best.depOffset, tofDays: best.tof,
      dvLaunchKms: +best.dvLaunch.toFixed(3),
      dvArriveKms: +best.dvArrive.toFixed(3),
      dvTotalKms: +best.dvTotal.toFixed(3),
    },
  };
}

// state vector -> classical elements (Curtis Alg 4.1), for sampling the transfer
export function rv2coe(r, v, mu) {
  const R = norm(r), V = norm(v), vr = dot(r, v) / R;
  const h = cross(r, v), H = norm(h);
  const inc = Math.acos(Math.max(-1, Math.min(1, h[2] / H)));
  const nvec = cross([0, 0, 1], h), n = norm(nvec);
  const evec = scale(sub(scale(r, V * V - mu / R), scale(v, R * vr)), 1 / mu);
  const e = norm(evec);
  let om = n ? Math.acos(Math.max(-1, Math.min(1, nvec[0] / n))) : 0;
  if (nvec[1] < 0) om = 2 * Math.PI - om;
  let w = (n && e) ? Math.acos(Math.max(-1, Math.min(1, dot(nvec, evec) / (n * e)))) : 0;
  if (evec[2] < 0) w = 2 * Math.PI - w;
  let nu = e ? Math.acos(Math.max(-1, Math.min(1, dot(evec, r) / (e * R)))) : 0;
  if (vr < 0) nu = 2 * Math.PI - nu;
  const a = (H * H / mu) / (1 - e * e);
  return { a, e, i: inc, om, w, nu };
}

// sample the actual Lambert transfer arc between Earth(dep) and asteroid(arr)
export function transferPath(el, depJd, tof, segments = 96) {
  const [rE] = earthState(depJd);
  const [rA] = propagate(el, depJd + tof);
  const sol = lambert(rE, rA, tof, MU_SUN, true);
  if (!sol) return null;
  const co = rv2coe(rE, sol[0], MU_SUN);
  const c2 = rv2coe(rA, sol[1], MU_SUN);
  let dnu = c2.nu - co.nu;
  dnu = ((dnu % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
  const pts = [];
  for (let k = 0; k <= segments; k++) {
    const nu = co.nu + dnu * (k / segments);
    const r = (co.a * (1 - co.e * co.e)) / (1 + co.e * Math.cos(nu));
    pts.push(rotate(r * Math.cos(nu), r * Math.sin(nu), co.om, co.i, co.w));
  }
  return pts;
}

export const todayJd = () => 2440587.5 + Date.now() / 86400000;
