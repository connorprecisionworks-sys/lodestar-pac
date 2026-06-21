import { useEffect, useRef } from "react";

function lerp(a, b, t) { return a + (b - a) * t; }
function color(dv, lo, span) {
  const t = Math.min(Math.max((dv - lo) / span, 0), 1);
  // cyan (low / best) -> teal -> dark (high)
  let r, g, b;
  if (t < 0.5) { const u = t / 0.5; r = lerp(70, 47, u); g = lerp(223, 153, u); b = lerp(230, 160, u); }
  else { const u = (t - 0.5) / 0.5; r = lerp(47, 28, u); g = lerp(153, 32, u); b = lerp(160, 38, u); }
  return `rgb(${r | 0},${g | 0},${b | 0})`;
}

export default function PorkchopPlot({ data }) {
  const ref = useRef(null);
  useEffect(() => {
    const cv = ref.current;
    if (!cv || !data?.grid) return;
    const grid = data.grid, tofs = data.tofs, deps = data.depOffsets;
    const nr = grid.length, nc = grid[0].length;
    const W = cv.clientWidth || 380, H = 220, padL = 38, padB = 26, padT = 6, padR = 6;
    cv.width = W; cv.height = H;
    const x = cv.getContext("2d");
    x.clearRect(0, 0, W, H);

    const flat = grid.flat().filter((v) => v != null);
    if (!flat.length) return;
    const lo = Math.min(...flat);
    const span = 14; // km/s window above optimum for the color ramp

    const gw = (W - padL - padR) / nc, gh = (H - padT - padB) / nr;
    for (let ri = 0; ri < nr; ri++) {
      for (let ci = 0; ci < nc; ci++) {
        const dv = grid[ri][ci];
        x.fillStyle = dv == null ? "#0c0e11" : color(dv, lo, span);
        x.fillRect(padL + ci * gw, padT + (nr - 1 - ri) * gh, Math.ceil(gw), Math.ceil(gh));
      }
    }
    // optimum marker
    const o = data.optimal;
    if (o) {
      const ci = deps.indexOf(o.depOffsetDays);
      const ri = tofs.indexOf(o.tofDays);
      if (ci >= 0 && ri >= 0) {
        const cx = padL + (ci + 0.5) * gw, cy = padT + (nr - 1 - ri + 0.5) * gh;
        x.strokeStyle = "#fff"; x.lineWidth = 1.5;
        x.beginPath(); x.arc(cx, cy, 5, 0, 7); x.stroke();
        x.beginPath(); x.moveTo(cx - 9, cy); x.lineTo(cx + 9, cy);
        x.moveTo(cx, cy - 9); x.lineTo(cx, cy + 9); x.stroke();
      }
    }
    // axes
    x.fillStyle = "#878d96"; x.font = "9px 'JetBrains Mono',monospace";
    x.fillText("TOF", 4, padT + 8);
    x.fillText(tofs[0] + "d", 4, H - padB);
    x.fillText(tofs[tofs.length - 1] + "d", 4, padT + 8 + 10);
    x.fillText("DEPART (months from now)", padL, H - 8);
    const months = Math.round(deps[deps.length - 1] / 30);
    x.fillText("0", padL, H - padB + 12);
    x.fillText("+" + months + "mo", W - padR - 30, H - padB + 12);
  }, [data]);

  return <canvas ref={ref} className="porkchop" />;
}
