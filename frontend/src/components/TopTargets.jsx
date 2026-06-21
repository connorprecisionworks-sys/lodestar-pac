import { useEffect, useState } from "react";
import { source } from "../api/source.js";
import { prospectivity } from "../lib/mining.js";
import { fmtUSD } from "../lib/format.js";

export default function TopTargets({ meta, selectedId, onSelect }) {
  const [rows, setRows] = useState([]);

  useEffect(() => {
    if (!meta) return;
    let alive = true;
    source.allRecords().then((recs) => {
      if (!alive) return;
      const scored = recs
        .filter((r) => r.value_usd != null && r.dv_kms != null)
        .map((r) => ({ id: r.id, full_name: r.full_name, value_complex: r.value_complex,
          value_usd: r.value_usd, dv_kms: r.dv_kms, type_source: r.type_source,
          prosp: prospectivity(r, meta) }));
      scored.sort((a, b) => b.prosp - a.prosp);
      setRows(scored.slice(0, 12));
    });
    return () => { alive = false; };
  }, [meta]);

  return (
    <div className="panel">
      <h2 data-idx="05">Top Mining Targets <span className="note">value · accessibility · composition confidence, fused</span></h2>
      <div className="table-scroll">
        <table className="ranktable">
          <thead><tr>
            <th className="idxcol">#</th><th>Object</th><th>Type</th>
            <th className="num">Prospectivity</th><th className="num">Est. value</th><th className="num">Δv</th>
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.id} className={r.id === selectedId ? "sel" : ""} onClick={() => onSelect(r.id)}>
                <td className="idxcol mono faint">{String(i + 1).padStart(2, "0")}</td>
                <td className="objcell">
                  <span className="oname">{r.full_name.trim()}</span>
                  {r.type_source !== "measured" && <span className={r.type_source === "ml-predicted" ? "pred" : "est"}>{r.type_source === "ml-predicted" ? "pred" : "est"}</span>}
                </td>
                <td><span className={"pill " + r.value_complex}>{r.value_complex}</span></td>
                <td className="num"><span className="prospbar"><i style={{ width: r.prosp + "%" }} /></span><span className="mono score">{r.prosp}</span></td>
                <td className="num mono val">{fmtUSD(r.value_usd)}</td>
                <td className="num mono">{r.dv_kms.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
