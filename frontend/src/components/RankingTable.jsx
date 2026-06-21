import { fmtUSD } from "../lib/format.js";

const COLS = [
  ["full_name", "Object"],
  ["value_complex", "Type"],
  ["value_usd", "Est. value", "num"],
  ["dv_kms", "Δv", "num"],
  ["display_diameter_km", "Ø km", "num"],
  ["score", "Score", "num"],
];

export default function RankingTable({ data, selectedId, onSelect, sort, onSort, page, onPage }) {
  const items = data?.items || [];
  const total = data?.total || 0;
  const pageSize = data?.page_size || 50;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="panel">
      <h2 data-idx="01">Ranked Targets <span className="note">{total.toLocaleString()} match filters</span></h2>
      <div className="table-scroll">
        <table className="ranktable">
          <thead>
            <tr>
              <th className="idxcol">#</th>
              {COLS.map(([k, label, cls]) => (
                <th key={k} className={(cls || "") + (sort === k ? " active" : "")} onClick={() => onSort(k)}>
                  {label}{sort === k ? " ↓" : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((r, i) => (
              <tr key={r.id} className={r.id === selectedId ? "sel" : ""} onClick={() => onSelect(r.id)}>
                <td className="idxcol mono faint">{String(page * pageSize + i + 1).padStart(2, "0")}</td>
                <td className="objcell">
                  <span className="oname">{r.full_name.trim()}</span>
                  {r.spec_is_assumed
                    ? <span className="est">est</span>
                    : r.spec_type && <span className="subtype">{r.spec_type}</span>}
                </td>
                <td>
                  <span className={"pill " + r.value_complex + (r.spec_is_assumed ? " dim" : "")}>{r.value_complex}</span>
                </td>
                <td className="num mono val">{fmtUSD(r.value_usd)}</td>
                <td className="num mono">
                  {r.dv_kms?.toFixed(2)}
                  {r.dv_source === "asterank-benner" && <span className="src">bnr</span>}
                </td>
                <td className="num mono faint">{r.display_diameter_km ? r.display_diameter_km.toFixed(1) : "—"}</td>
                <td className="num mono score">{r.score?.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <button disabled={page <= 0} onClick={() => onPage(page - 1)}>Prev</button>
        <span>{(page * pageSize + 1).toLocaleString()}–{Math.min((page + 1) * pageSize, total).toLocaleString()} / {total.toLocaleString()}</span>
        <button disabled={page >= pages - 1} onClick={() => onPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}
