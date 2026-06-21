export default function Controls({ q, weight, spec, dvMax, onChange }) {
  const wLabel = weight < 0.34 ? "favor access" : weight > 0.66 ? "favor value" : "balanced";
  return (
    <div className="panel controls">
      <div>
        <label>Priority: accessibility &harr; value <em>{wLabel}</em></label>
        <input type="range" min="0" max="100" value={Math.round(weight * 100)}
          onChange={(e) => onChange({ weight: +e.target.value / 100 })} />
        <div className="slabels"><span>easiest to reach</span><span>most valuable</span></div>
      </div>
      <div>
        <label>Spectral filter</label>
        <select value={spec} onChange={(e) => onChange({ spec: e.target.value })}>
          <option value="all">All objects</option>
          <option value="measured">Measured type only</option>
          <option value="M">M-type (metals)</option>
          <option value="S">S-type (stony)</option>
          <option value="C">C-type (volatiles)</option>
        </select>
      </div>
      <div>
        <label>Max delta-v: <span className="mono">{dvMax >= 40 ? "any" : dvMax.toFixed(1)}</span></label>
        <input type="range" min="3" max="40" step="0.5" value={dvMax}
          onChange={(e) => onChange({ dvMax: +e.target.value })} />
      </div>
      <div>
        <label>Search name / designation</label>
        <input type="text" value={q} placeholder="Apophis, Eros, 2008..."
          onChange={(e) => onChange({ q: e.target.value })} />
      </div>
    </div>
  );
}
