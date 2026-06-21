// Keplerian elements -> 3D ecliptic coordinates (AU). Used by the orbit viewer.
// Angles in degrees as stored; converted internally. Frame: ecliptic, Sun at origin.

const D2R = Math.PI / 180;

// Earth's orbit, for the reference ring.
export const EARTH = { a_au: 1.0, e: 0.0167, i_deg: 0, om_deg: 0, w_deg: 102.9, ma_deg: 0 };

// Rotate a perifocal point (xp, yp, 0) into the ecliptic frame.
function perifocalToEcliptic(xp, yp, om, inc, w) {
  const cO = Math.cos(om), sO = Math.sin(om);
  const ci = Math.cos(inc), si = Math.sin(inc);
  const cw = Math.cos(w), sw = Math.sin(w);
  const x = (cO * cw - sO * sw * ci) * xp + (-cO * sw - sO * cw * ci) * yp;
  const y = (sO * cw + cO * sw * ci) * xp + (-sO * sw + cO * cw * ci) * yp;
  const z = (sw * si) * xp + (cw * si) * yp;
  return [x, y, z];
}

function radiusAt(a, e, nu) {
  return (a * (1 - e * e)) / (1 + e * Math.cos(nu));
}

// Sample the full orbit as a flat array [x,y,z, x,y,z, ...] for a LineLoop.
export function orbitPoints(el, segments = 256) {
  const a = el.a_au, e = el.e;
  const om = (el.om_deg || 0) * D2R, inc = (el.i_deg || 0) * D2R, w = (el.w_deg || 0) * D2R;
  const out = new Float32Array(segments * 3);
  for (let k = 0; k < segments; k++) {
    const nu = (2 * Math.PI * k) / segments;
    const r = radiusAt(a, e, nu);
    const [x, y, z] = perifocalToEcliptic(r * Math.cos(nu), r * Math.sin(nu), om, inc, w);
    out[k * 3] = x; out[k * 3 + 1] = y; out[k * 3 + 2] = z;
  }
  return out;
}

// Solve Kepler's equation M = E - e sinE for E (radians).
function solveKepler(M, e) {
  let E = M;
  for (let n = 0; n < 60; n++) {
    const d = (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
    E -= d;
    if (Math.abs(d) < 1e-9) break;
  }
  return E;
}

// Position [x,y,z] at a given mean anomaly (degrees).
export function positionAtMeanAnomaly(el, maDeg) {
  const e = el.e;
  const M = (((maDeg % 360) + 360) % 360) * D2R;
  const E = solveKepler(M, e);
  const nu = 2 * Math.atan2(Math.sqrt(1 + e) * Math.sin(E / 2), Math.sqrt(1 - e) * Math.cos(E / 2));
  const r = radiusAt(el.a_au, e, nu);
  return perifocalToEcliptic(
    r * Math.cos(nu), r * Math.sin(nu),
    (el.om_deg || 0) * D2R, (el.i_deg || 0) * D2R, (el.w_deg || 0) * D2R
  );
}

// Schematic transfer arc between two points (a bezier bulged outward from the
// Sun). Illustrative only - the real transfer is Phase 2.
export function transferArc(p0, p1, segments = 80) {
  const mid = [(p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, (p0[2] + p1[2]) / 2];
  const mr = Math.hypot(mid[0], mid[1], mid[2]) || 1;
  const bulge = 1.25;
  const ctrl = [mid[0] / mr * mr * bulge, mid[1] / mr * mr * bulge, mid[2] / mr * mr * bulge];
  const out = new Float32Array((segments + 1) * 3);
  for (let k = 0; k <= segments; k++) {
    const t = k / segments, u = 1 - t;
    out[k * 3] = u * u * p0[0] + 2 * u * t * ctrl[0] + t * t * p1[0];
    out[k * 3 + 1] = u * u * p0[1] + 2 * u * t * ctrl[1] + t * t * p1[1];
    out[k * 3 + 2] = u * u * p0[2] + 2 * u * t * ctrl[2] + t * t * p1[2];
  }
  return out;
}
