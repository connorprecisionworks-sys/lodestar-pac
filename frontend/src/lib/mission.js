// Rocket-equation mission feasibility (Phase 3 of the scope). Turns a mission
// delta-v into the fuel-and-effort story: propellant mass fraction via the
// Tsiolkovsky equation, the chemical-vs-electric tradeoff, and a feasibility tier.

const G0 = 9.80665; // m/s^2

// Representative specific impulses (s).
export const ISP = { chemical: 320, electric: 3000 };

// Propellant mass fraction needed for a given delta-v (km/s) and engine Isp:
// pf = 1 - exp(-dv / (Isp*g0)). Fraction of the wet mass that must be propellant.
export function propellantFraction(dvKms, ispS) {
  if (dvKms == null) return null;
  return 1 - Math.exp(-(dvKms * 1000) / (ispS * G0));
}

// Feasibility tier from total mission delta-v (LEO to rendezvous, km/s).
export function feasibility(dvKms) {
  if (dvKms == null) return { tier: "unknown", label: "Unknown", color: "var(--faint)" };
  if (dvKms < 5) return { tier: "easy", label: "Highly accessible", color: "var(--lime)" };
  if (dvKms < 7) return { tier: "good", label: "Accessible", color: "var(--lime-dim)" };
  if (dvKms < 10) return { tier: "moderate", label: "Moderate", color: "var(--s)" };
  if (dvKms < 15) return { tier: "hard", label: "Challenging", color: "#d6803f" };
  return { tier: "veryhard", label: "Very hard", color: "var(--m)" };
}

// Full mission readout for a delta-v.
export function missionProfile(dvKms) {
  if (dvKms == null) return null;
  return {
    dvKms,
    feasibility: feasibility(dvKms),
    chemical: propellantFraction(dvKms, ISP.chemical),
    electric: propellantFraction(dvKms, ISP.electric),
  };
}
