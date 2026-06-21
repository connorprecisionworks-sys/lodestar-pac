import { useEffect, useRef, useState } from "react";
// Static data source (no backend) by default; swap to ./api/client.js for a live API.
import { source as api } from "./api/source.js";
import Controls from "./components/Controls.jsx";
import RankingTable from "./components/RankingTable.jsx";
import DetailPanel from "./components/DetailPanel.jsx";
import OrbitViewer from "./components/OrbitViewer.jsx";

export default function App() {
  const [ctrl, setCtrl] = useState({ weight: 0.5, spec: "all", dvMax: 40, q: "" });
  const [sort, setSort] = useState("score");
  const [page, setPage] = useState(0);
  const [data, setData] = useState(null);
  const [meta, setMeta] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [trajectory, setTrajectory] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const timer = useRef(null);

  useEffect(() => { api.meta().then(setMeta).catch((e) => setErr(String(e))); }, []);

  // debounced list fetch on any control / sort / page change
  useEffect(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      api.asteroids({
        weight: ctrl.weight, spec: ctrl.spec,
        dv_max: ctrl.dvMax >= 40 ? undefined : ctrl.dvMax,
        q: ctrl.q, sort, page, page_size: 50,
      }).then(setData).catch((e) => setErr(String(e)));
    }, 220);
    return () => clearTimeout(timer.current);
  }, [ctrl, sort, page]);

  // load detail when selection changes
  useEffect(() => {
    if (selectedId == null) return;
    setTrajectory(null);
    api.detail(selectedId).then(setDetail).catch((e) => setErr(String(e)));
  }, [selectedId]);

  const onChange = (partial) => { setCtrl((c) => ({ ...c, ...partial })); setPage(0); };
  const onSort = (k) => { setSort(k); setPage(0); };
  const onCompute = (id) => {
    setBusy(true);
    api.trajectory(id).then(setTrajectory).catch((e) => setErr(String(e))).finally(() => setBusy(false));
  };

  return (
    <div className="wrap">
      <header>
        <div className="brandrow">
          <div className="mark" />
          <h1>Lodestar <span className="pac">PAC</span></h1>
        </div>
        <div className="subbar">
          <span className="eyebrow"><b>Predictive Asteroid Characterization</b></span>
          <span className="eyebrow">Prospecting Console</span>
          <span className="eyebrow">Near-Earth Catalog</span>
          <span className="eyebrow">Phase 1</span>
        </div>
        {meta && (
          <div className="telem">
            <div className="cell"><div className="k">Catalog objects</div><div className="v">{meta.n.toLocaleString()}</div></div>
            <div className="cell"><div className="k">Measured types</div><div className="v">{meta.measured_spec.toLocaleString()}</div></div>
            <div className="cell"><div className="k">Benner Δv refs</div><div className="v accent">{meta.benner_dv.toLocaleString()}</div></div>
            <div className="cell"><div className="k">Δv envelope</div><div className="v">{meta.dv_range[0].toFixed(1)}–{meta.dv_range[1].toFixed(0)} km/s</div></div>
            <div className="cell"><div className="k">Value model</div><div className="v accent">Computed</div></div>
          </div>
        )}
      </header>

      {err && <div className="err">FAULT // could not load dataset: {err}</div>}

      <Controls q={ctrl.q} weight={ctrl.weight} spec={ctrl.spec} dvMax={ctrl.dvMax} onChange={onChange} />

      <div className="main">
        <RankingTable data={data} selectedId={selectedId} onSelect={setSelectedId}
          sort={sort} onSort={onSort} page={page} onPage={setPage} />
        <div className="rightcol">
          <div className="panel viewerpanel">
            <h2 data-idx="02">Orbit View <span className="note">Heliocentric · real elements</span></h2>
            <OrbitViewer detail={detail} trajectory={trajectory} />
          </div>
          <DetailPanel detail={detail} trajectory={trajectory} busy={busy} onCompute={onCompute} />
        </div>
      </div>

      <footer>
        <span className="lime">▮</span> L1 Ingestion · L3 Screening Δv · L4 Ranking — Operational &nbsp;//&nbsp; L2 ML Characterization (Phase 4) · Launch-Window Simulation (Phase 2) — Pending<br />
        Orbits rendered from real Keplerian elements · Transfer arc schematic until Phase 2 · All figures estimates with uncertainty, never measurements
      </footer>
    </div>
  );
}
