import { fmtQty, fmtUSD } from "../lib/format.js";
import { GROUP_COLOR, groupFractions, materialsFor } from "../lib/materials.js";

const GROUPS = ["metal", "silicate", "volatile", "precious"];

export default function MaterialBreakdown({ complex, diameterKm }) {
  if (!complex || !diameterKm) return null;
  const mats = materialsFor(complex, diameterKm);
  const gf = groupFractions(complex);
  const total = GROUPS.reduce((s, g) => s + gf[g], 0) || 1;

  return (
    <div className="matbox">
      <div className="matbar">
        {GROUPS.map((g) => gf[g] > 0 && (
          <span key={g} title={g} style={{ width: `${(gf[g] / total) * 100}%`, background: GROUP_COLOR[g] }} />
        ))}
      </div>
      <div className="matlist">
        {mats.map((m) => (
          <div className="matrow" key={m.name}>
            <span className="sw" style={{ background: m.color }} />
            <span className="mn">{m.name}</span>
            <span className="ma mono">{m.group === "precious" ? `${fmtQty(m.kg)} kg` : `${fmtQty(m.kg / 1000)} t`}</span>
            <span className="mv mono">{fmtUSD(m.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
