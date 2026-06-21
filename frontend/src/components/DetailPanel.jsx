import { fmtQty, fmtUSD, jdToDate } from "../lib/format.js";
import { missionProfile } from "../lib/mission.js";
import { missionCost, prospectivity, valueToCost } from "../lib/mining.js";
import PorkchopPlot from "./PorkchopPlot.jsx";
import AsteroidSpecimen from "./AsteroidSpecimen.jsx";
import MaterialBreakdown from "./MaterialBreakdown.jsx";

function Row({ k, v }) {
  return <div className="kv"><span>{k}</span><span className="mono">{v}</span></div>;
}

export default function DetailPanel({ detail, trajectory, busy, onCompute, meta }) {
  if (!detail) {
    return <div className="panel"><h2 data-idx="03">Object Detail</h2>
      <p className="note">Select a target from the table to load its orbit, value breakdown, and run a trajectory estimate.</p></div>;
  }
  return (
    <div className="panel">
      <h2 data-idx="03">{detail.full_name.trim()}</h2>
      <Row k="Complex" v={`${detail.value_complex} (${
        detail.type_source === "measured" ? "measured"
          : detail.type_source === "ml-predicted"
            ? `ML-predicted, ${Math.round((detail.ml_confidence || 0) * 100)}% conf`
            : "assumed"})`} />
      <Row k="Est. value" v={fmtUSD(detail.value_usd)} />
      <Row k="Value range" v={`${fmtUSD(detail.value_low)} - ${fmtUSD(detail.value_high)}`} />
      <Row k="Delta-v" v={`${detail.dv_kms?.toFixed(2)} km/s (${detail.dv_source === "asterank-benner" ? "Benner" : "proxy"})`} />
      <Row k="Size" v={detail.display_diameter_km ? detail.display_diameter_km.toFixed(2) + " km" : "-"} />
      <Row k="Orbit a / e / i" v={`${detail.a_au} au / ${detail.e} / ${detail.i_deg}°`} />

      <h3>Specimen</h3>
      <AsteroidSpecimen detail={detail} />

      {detail.water_tons != null && (
        <>
          <h3>Estimated composition</h3>
          <MaterialBreakdown complex={detail.value_complex} diameterKm={detail.display_diameter_km} />
        </>
      )}

      {(() => {
        const mp = missionProfile(detail.dv_kms);
        if (!mp) return null;
        return (
          <>
            <h3>Mission feasibility</h3>
            <Row k="Accessibility" v={<span style={{ color: mp.feasibility.color }}>{mp.feasibility.label} · {detail.dv_kms.toFixed(1)} km/s</span>} />
            <Row k="Propellant, chemical" v={`${Math.round(mp.chemical * 100)}% of ship mass`} />
            <Row k="Propellant, electric" v={`${Math.round(mp.electric * 100)}% of ship mass`} />
          </>
        );
      })()}

      {meta && detail.value_usd != null && (
        <>
          <h3>Mining assessment</h3>
          <Row k="Prospectivity" v={`${prospectivity(detail, meta)} / 100`} />
          <Row k="Est. mission cost" v={fmtUSD(missionCost(detail.dv_kms))} />
          <Row k="Value-to-cost" v={`${fmtQty(valueToCost(detail))}×`} />
        </>
      )}

      <button className="primary" disabled={busy} onClick={() => onCompute(detail.id)}>
        {busy ? "Computing launch windows..." : "Compute trajectory"}
      </button>

      {trajectory?.mode === "porkchop" && trajectory.optimal && (
        <div className="traj">
          <h3>Optimal launch window</h3>
          <Row k="Depart" v={jdToDate(trajectory.startJd + trajectory.optimal.depOffsetDays)} />
          <Row k="Flight time" v={`${trajectory.optimal.tofDays} days`} />
          <Row k="Departure burn" v={`${trajectory.optimal.dvLaunchKms} km/s`} />
          <Row k="Arrival / match" v={`${trajectory.optimal.dvArriveKms} km/s`} />
          <Row k="Total Δv" v={`${trajectory.optimal.dvTotalKms} km/s`} />
          <PorkchopPlot data={trajectory} />
          <p className="note small">{trajectory.phase2_note}</p>
        </div>
      )}

      {trajectory?.mode === "porkchop" && !trajectory.optimal && (
        <p className="note small">No feasible transfer found within the search window.</p>
      )}

      {trajectory?.mode === "screening" && (
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
