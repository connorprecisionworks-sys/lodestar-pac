// In-depth material breakdown, computed from compositional complex + size.
// Illustrative / order-of-magnitude, consistent in spirit with the backend value
// model. Fractions are recoverable mass fractions by complex; the remainder is
// unmodeled rock. Groups drive the 3D composition shells.

const DENSITY = { C: 1300, S: 2700, M: 5300 }; // kg/m^3

export const MATERIALS = [
  { name: "Water ice", group: "volatile", color: "#5ad1e6", usd: 5, frac: { C: 0.10, S: 0.001, M: 0 } },
  { name: "Organics", group: "volatile", color: "#8a7a5e", usd: 0.2, frac: { C: 0.10, S: 0.01, M: 0 } },
  { name: "Silicates", group: "silicate", color: "#c9a36b", usd: 0.05, frac: { C: 0.40, S: 0.55, M: 0.02 } },
  { name: "Iron", group: "metal", color: "#9aa0a6", usd: 0.5, frac: { C: 0.015, S: 0.12, M: 0.70 } },
  { name: "Nickel", group: "metal", color: "#c3ccd4", usd: 15, frac: { C: 0.005, S: 0.03, M: 0.17 } },
  { name: "Cobalt", group: "metal", color: "#6e8bd6", usd: 33, frac: { C: 0.0005, S: 0.001, M: 0.006 } },
  { name: "Platinum-group", group: "precious", color: "#e6d27a", usd: 35000, frac: { C: 0, S: 1e-6, M: 3e-5 } },
  { name: "Gold", group: "precious", color: "#f3c64a", usd: 60000, frac: { C: 0, S: 1e-7, M: 5e-6 } },
];

export const GROUP_COLOR = {
  metal: "#9aa0a6", silicate: "#c9a36b", volatile: "#5ad1e6", precious: "#f3c64a",
};

export function massKg(diameterKm, complex) {
  if (!diameterKm || diameterKm <= 0) return null;
  const r = (diameterKm * 1000) / 2;
  return (4 / 3) * Math.PI * r ** 3 * (DENSITY[complex] || DENSITY.S);
}

// Per-object material list: { name, color, group, kg, value } sorted by value.
export function materialsFor(complex, diameterKm) {
  const m = massKg(diameterKm, complex);
  if (m == null) return [];
  return MATERIALS
    .map((mat) => {
      const f = mat.frac[complex] || 0;
      return { name: mat.name, color: mat.color, group: mat.group, kg: m * f, value: m * f * mat.usd };
    })
    .filter((x) => x.kg > 0)
    .sort((a, b) => b.value - a.value);
}

// Group mass-fractions (for the 3D shells), normalized to the modeled total.
export function groupFractions(complex) {
  const g = { metal: 0, silicate: 0, volatile: 0, precious: 0 };
  for (const mat of MATERIALS) g[mat.group] += mat.frac[complex] || 0;
  const total = g.metal + g.silicate + g.volatile + g.precious || 1;
  return {
    metal: g.metal / total, silicate: g.silicate / total,
    volatile: g.volatile / total, precious: g.precious / total,
  };
}
