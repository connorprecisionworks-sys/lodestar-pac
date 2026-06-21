function fmtUSD(v) {
  if (v == null) return "-";
  if (v >= 1e15) return "$" + (v / 1e15).toFixed(1) + "Q";
  if (v >= 1e12) return "$" + (v / 1e12).toFixed(1) + "T";
  if (v >= 1e9) return "$" + (v / 1e9).toFixed(1) + "B";
  if (v >= 1e6) return "$" + (v / 1e6).toFixed(1) + "M";
  return "$" + Math.round(v);
}

const COLS = [
  ["full_name", "Object"],
  ["value_complex", "Type"],
  ["value_usd", "Est. value", "num"],
  ["dv_kms", "Δv km/s", "num"],
  ["display_diameter_km", "Size km", "num"],
  ["score", "Score", "num"],
];

export default function RankingTable({ data, selectedId, onSelect, sort, onSort, page, onPage }) {
  const items = data?.items || [];
  const total = data?.total || 0;
  const pages = Math.max(1, Math.ceil(total / (data?.page_size || 50)));
  return (
    <div className="panel">
      <h2 data-idx="01">Ranked Targets <span className="note">{total.toLocaleString()} match filters</span></h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th>
              {COLS.map(([k, label, cls]) => (
                <th key={k} className={cls} onClick={() => onSort(k)}>
                  {label}{sort === k ? " ▾" : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((r, i) => (
              <tr key={r.id} className={r.id === selectedId ? "sel" : ""} onClick={() => onSelect(r.id)}>
                <td className="mono faint">{page * (data.page_size) + i + 1}</td>
                <td>{r.full_name.trim()}
                  <br /><span className="tagk">
                    {r.spec_type ? r.spec_type : "unmeasured"}
                    {r.spec_is_assumed ? <em className="assumed"> assumed</em> : ""}
                  </span>
                </td>
                <td><span className={"pill " + r.value_complex}>{r.value_complex}</span></td>
                <td className="num mono">{fmtUSD(r.value_usd)}
                  <br /><span className="band">{fmtUSD(r.value_low)} - {fmtUSD(r.value_high)}</span>
                </td>
                <td className="num mono">{r.dv_kms?.toFixed(2)}
                  <span className={"tagk " + (r.dv_source === "asterank-benner" ? "benner" : "")}>
                    {r.dv_source === "asterank-benner" ? " benner" : " proxy"}
                  </span>
                </td>
                <td className="num mono">{r.display_diameter_km ? r.display_diameter_km.toFixed(2) : "-"}</td>
                <td className="num mono">{r.score?.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <button disabled={page <= 0} onClick={() => onPage(page - 1)}>&larr; Prev</button>
        <span>Page {page + 1} of {pages}</span>
        <button disabled={page >= pages - 1} onClick={() => onPage(page + 1)}>Next &rarr;</button>
      </div>
    </div>
  );
}
