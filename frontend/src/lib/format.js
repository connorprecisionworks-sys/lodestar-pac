// Compact USD with proper unit rolling and 3 significant figures, so values
// never overflow a unit (no "$1350.0Q"). Suffixes go up to quintillion.
const TIERS = [
  ["Qi", 1e18], ["Qa", 1e15], ["T", 1e12], ["B", 1e9], ["M", 1e6], ["K", 1e3],
];

export function fmtUSD(v) {
  if (v == null || Number.isNaN(v)) return "—";
  for (const [s, m] of TIERS) {
    if (Math.abs(v) >= m) {
      const x = v / m;
      const mant = x >= 100 ? x.toFixed(0) : x >= 10 ? x.toFixed(1) : x.toFixed(2);
      return "$" + mant + s;
    }
  }
  return "$" + Math.round(v);
}

export function fmtNum(v, dp = 2) {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(dp);
}
