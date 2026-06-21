function fmtUSD(v) {
  if (v == null) return "-";
  if (v >= 1e15) return "$" + (v / 1e15).toFixed(2) + "Q";
  if (v >= 1e12) return "$" + (v / 1e12).toFixed(2) + "T";
  if (v >= 1e9) return "$" + (v / 1e9).toFixed(2) + "B";
  if (v >= 1e6) return "$" + (v / 1e6).toFixed(2) + "M";
  return "$" + Math.round(v);
}

function Row({ k, v }) {
  return <div className="kv"><span>{k}</span><span className="mono">{v}</span></div>;
}

export default function DetailPanel({ detail, trajectory, busy, onCompute }) {
  if (!detail) {
    return <div className="panel"><h2>Object detail</h2>
      <p className="note">Select an asteroid from the table to see its orbit, value breakdown, and run a trajectory estimate.</p></div>;
  }
  return (
    <div className="panel">
      <h2>{detail.full_name.trim()}</h2>
      <Row k="Complex" v={detail.value_complex + (detail.spec_is_assumed ? " (assumed)" : " (measured)")} />
      <Row k="Est. value" v={fmtUSD(detail.value_usd)} />
      <Row k="Value range" v={`${fmtUSD(detail.value_low)} - ${fmtUSD(detail.value_high)}`} />
      <Row k="Delta-v" v={`${detail.dv_kms?.toFixed(2)} km/s (${detail.dv_source === "asterank-benner" ? "Benner" : "proxy"})`} />
      <Row k="Size" v={detail.display_diameter_km ? detail.display_diameter_km.toFixed(2) + " km" : "-"} />
      <Row k="Orbit a / e / i" v={`${detail.a_au} au / ${detail.e} / ${detail.i_deg}°`} />

      <button className="primary" disabled={busy} onClick={() => onCompute(detail.id)}>
        {busy ? "Computing..." : "Compute trajectory"}
      </button>

      {trajectory && (
        <div className="traj">
          <h3>Screening transfer</h3>
          <Row k="Headline Δv" v={`${trajectory.dv_headline_kms?.toFixed(2)} km/s`} />
          <Row k="Departure burn" v={`${trajectory.breakdown.dv_launch_kms} km/s`} />
          <Row k="Arrival / match" v={`${trajectory.breakdown.dv_arrive_kms} km/s`} />
          <Row k="Proxy total" v={`${trajectory.breakdown.dv_total_kms} km/s ±${Math.round(trajectory.breakdown.rel_uncertainty * 100)}%`} />
          <p className="note small">{trajectory.phase2_note}</p>
        </div>
      )}
    </div>
  );
}
