import { useMemo, useState } from "react";
import { roundTrip, todayJd } from "../lib/astro.js";
import { VEHICLES, ENGINES, missionEconomics } from "../lib/vehicles.js";
import { fmtUSD, jdToDate } from "../lib/format.js";

const T0 = todayJd(); // fixed launch reference for the session
const fmtT = (t) => (t >= 1000 ? (t / 1000).toFixed(t >= 10000 ? 0 : 1) + "k" : Math.round(t).toString());
const fmtDur = (d) => (d >= 365 ? (d / 365.25).toFixed(1) + " yr" : d + " d");

function Row({ k, v, accent }) {
  return <div className="kv"><span>{k}</span><span style={accent ? { color: "var(--lime)" } : null}>{v}</span></div>;
}

export default function MissionPlanner({ detail }) {
  const [stay, setStay] = useState(180);
  const [vehId, setVehId] = useState("starship");
  const [engId, setEngId] = useState("electric");

  const el = useMemo(() => {
    if (detail?.epoch_jd == null || detail?.a_au == null || detail?.ma_deg == null) return null;
    return { a: detail.a_au, e: detail.e, i: detail.i_deg, om: detail.om_deg, w: detail.w_deg, ma: detail.ma_deg, epoch: detail.epoch_jd };
  }, [detail]);

  const rt = useMemo(() => (el ? roundTrip(el, T0, { stayDays: stay }) : null), [el, stay]);
  const vehicle = VEHICLES.find((v) => v.id === vehId);
  const engine = ENGINES.find((e) => e.id === engId);
  const complex = detail?.value_complex || "S";
  const econ = useMemo(
    () => (rt ? missionEconomics({ vehicle, engine, rt, complex }) : null),
    [rt, vehicle, engine, complex],
  );

  if (!el) {
    return (
      <>
        <h3>Round-trip mission</h3>
        <p className="note small">Needs orbital elements with an epoch. Re-run the data pipeline to unlock the round-trip planner for this object.</p>
      </>
    );
  }
  if (!rt) {
    return (<><h3>Round-trip mission</h3><p className="note small">No closed round trip found in the search window.</p></>);
  }

  // timeline segment widths (% of total duration)
  const tot = rt.totalDurationDays;
  const pOut = (rt.tofOutDays / tot) * 100, pStay = (stay / tot) * 100, pRet = (rt.tofRetDays / tot) * 100;
  const variant = econ.capture; // propulsive-capture variant
  const aero = econ.aero;

  return (
    <>
      <h3>Round-trip mission · mine &amp; return</h3>

      <div className="seg">
        {ENGINES.map((e) => (
          <button key={e.id} className={"segbtn" + (e.id === engId ? " on" : "")} onClick={() => setEngId(e.id)}>{e.name.split(" ")[0]}</button>
        ))}
      </div>
      <div className="seg">
        {VEHICLES.map((v) => (
          <button key={v.id} className={"segbtn sm" + (v.id === vehId ? " on" : "")} onClick={() => setVehId(v.id)}>{v.name}</button>
        ))}
      </div>

      <div className="mpstay">
        <label>Mining stay <em>{stay} days</em></label>
        <input type="range" min="30" max="540" step="15" value={stay} onChange={(e) => setStay(+e.target.value)} />
      </div>

      {/* itinerary timeline */}
      <div className="mptl">
        <div className="mptl-bar">
          <span className="seg-out" style={{ width: pOut + "%" }} title="outbound" />
          <span className="seg-stay" style={{ width: pStay + "%" }} title="mining" />
          <span className="seg-ret" style={{ width: pRet + "%" }} title="return" />
        </div>
        <div className="mptl-leg"><b>Outbound</b> {fmtDur(rt.tofOutDays)} · <b>Mine</b> {fmtDur(stay)} · <b>Return</b> {fmtDur(rt.tofRetDays)}</div>
      </div>

      <Row k="Total mission" v={`${fmtDur(tot)} (${fmtT(tot)} days)`} accent />
      <Row k="Launch" v={jdToDate(T0 + rt.depOffsetDays)} />
      <Row k="Arrive / begin mining" v={jdToDate(T0 + rt.arriveOffsetDays)} />
      <Row k="Depart asteroid" v={jdToDate(T0 + rt.returnDepartOffsetDays)} />
      <Row k="Back at Earth" v={jdToDate(T0 + rt.returnArriveOffsetDays)} />

      <h3 style={{ marginTop: 16 }}>Δv budget</h3>
      <Row k="Launch (LEO → transfer)" v={`${rt.dvLaunchKms} km/s`} />
      <Row k="Rendezvous (match)" v={`${rt.dvArriveKms} km/s`} />
      <Row k="Depart asteroid" v={`${rt.dvReturnDepartKms} km/s`} />
      <Row k="Earth capture (to LEO)" v={`${rt.dvEarthCaptureKms} km/s`} />
      <Row k="Total Δv · propulsive capture" v={`${rt.dvTotalCaptureKms} km/s`} accent />
      <Row k="Total Δv · aerocapture" v={`${rt.dvTotalAeroKms} km/s`} accent />

      <h3 style={{ marginTop: 16 }}>Returnable cargo · {vehicle.name} · {engine.name.split(" ")[0]}</h3>
      {!variant.feasible && !aero.feasible ? (
        <p className="note small">This vehicle + engine cannot close the round trip at {rt.dvOutKms} km/s outbound — too little mass survives to the asteroid to carry any return propellant. Switch to solar-electric, or pick a heavier launcher.</p>
      ) : (
        <>
          <Row k="Aerocapture · cargo" v={`${aero.cargoTons.toLocaleString()} t`} accent />
          <Row k="Aerocapture · in-space value" v={fmtUSD(aero.valueInSpaceUsd)} />
          <Row k="Aerocapture · Earth-market" v={fmtUSD(aero.valueEarthUsd)} />
          <Row k="Capture-to-LEO · cargo" v={`${variant.cargoTons.toLocaleString()} t`} />
          <Row k="Capture-to-LEO · in-space value" v={fmtUSD(variant.valueInSpaceUsd)} />
        </>
      )}

      <p className="note small">
        Two-body Lambert round trip; rocket-equation return-mass balance. Vehicle payloads, Isp ({engine.ispS}s),
        15% dry/plant fraction, ${"" + (2000).toLocaleString()}/kg launch-cost-avoided and a blended ${econ.valuePerKg.toFixed(2)}/kg
        Earth price for {complex}-type are all screening assumptions, not measurements.
      </p>
    </>
  );
}
