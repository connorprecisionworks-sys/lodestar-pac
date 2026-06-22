// Launch vehicles + a return-cargo rocket model for the mining round trip.
//
// The idea: a rocket lifts a wet mass to LEO. That spacecraft flies out, mines a
// chunk, processes it, and flies the processed mass home. A two-phase Tsiolkovsky
// (rocket-equation) balance decides how much mass can actually come back.
//
// EVERY number here is an assumption for screening, not a measurement. Payloads
// are approximate published figures; Isp and dry-mass fractions are notional.

const G0 = 9.80665; // m/s^2

// Approximate published payload-to-LEO (metric tons). Expendable where relevant.
export const VEHICLES = [
  { id: "electron", name: "Electron", payloadLeoT: 0.3, note: "small-lift" },
  { id: "f9", name: "Falcon 9", payloadLeoT: 22.8, note: "expendable" },
  { id: "ng", name: "New Glenn", payloadLeoT: 45, note: "heavy-lift" },
  { id: "fh", name: "Falcon Heavy", payloadLeoT: 63.8, note: "expendable" },
  { id: "sls", name: "SLS Block 1", payloadLeoT: 95, note: "super-heavy" },
  { id: "starship", name: "Starship", payloadLeoT: 100, note: "refuel for more" },
];

// In-space propulsion options the user picks. Chemical = fast, thirsty;
// solar-electric = slow but sips propellant (huge effective Isp).
export const ENGINES = [
  { id: "chemical", name: "Chemical (bipropellant)", ispS: 350 },
  { id: "electric", name: "Solar-electric (SEP)", ispS: 3000 },
];

// Fraction of the LEO wet mass that is dry spacecraft + mining/processing plant.
// Scales the rig to the rocket, so a bigger launcher carries a bigger plant.
export const DRY_FRAC = 0.15;

// Bulk processed value, $/kg, blended across everything recoverable in the body
// (the "melt the chunk and bring it back" assumption — no cherry-picking veins).
import { MATERIALS } from "./materials.js";
export function bulkValuePerKg(complex) {
  return MATERIALS.reduce((s, m) => s + (m.frac[complex] || 0) * m.usd, 0);
}

// Material parked in space is worth at least what it would cost to launch the
// same mass from Earth. This is the "build rockets in space" value — the real
// case for hauling a chunk home to a cislunar depot instead of selling it.
export const LAUNCH_COST_PER_KG = 2000; // assumed $/kg to LEO

// How much processed cargo a vehicle can return.
//   Phase A (outbound, dvOut): W in LEO -> m_ast at the asteroid.
//   Phase B (return,  dvBack): (dry+cargo+returnProp) -> (dry+cargo).
// Solve the balance m_ast = dry + returnProp for the cargo mass.
// Returns tons; cargoTons <= 0 means the vehicle/engine cannot bring mass home.
export function returnableCargo({ payloadLeoT, dvOutKms, dvBackKms, ispS, dryFrac = DRY_FRAC }) {
  const ve = ispS * G0 / 1000; // km/s
  const W = payloadLeoT;
  const dry = dryFrac * W;
  const mAst = W * Math.exp(-dvOutKms / ve); // mass delivered to the asteroid
  const Rb = Math.exp(dvBackKms / ve);
  const dryPlusCargo = (mAst - dry) / (Rb - 1);
  const cargoTons = dryPlusCargo - dry;
  const returnPropTons = mAst - dry;
  return {
    massAtAsteroidT: +mAst.toFixed(3),
    dryT: +dry.toFixed(3),
    returnPropT: +Math.max(returnPropTons, 0).toFixed(3),
    cargoTons: cargoTons > 0 ? +cargoTons.toFixed(3) : 0,
    feasible: cargoTons > 0,
  };
}

// Full economics for one vehicle + engine + round-trip dv profile + composition.
// Computes both Earth-arrival variants (propulsive capture vs aerocapture).
export function missionEconomics({ vehicle, engine, rt, complex }) {
  const vpk = bulkValuePerKg(complex); // $/kg, Earth commodity
  const dvOut = rt.dvOutKms;
  const variant = (dvBack) => {
    const cargo = returnableCargo({
      payloadLeoT: vehicle.payloadLeoT, dvOutKms: dvOut, dvBackKms: dvBack, ispS: engine.ispS,
    });
    const kg = cargo.cargoTons * 1000;
    return {
      ...cargo, dvBackKms: +dvBack.toFixed(3),
      valueEarthUsd: kg * vpk,                 // sold as Earth commodity
      valueInSpaceUsd: kg * LAUNCH_COST_PER_KG, // kept in space, launch cost avoided
    };
  };
  return {
    valuePerKg: vpk,
    capture: variant(rt.dvReturnDepartKms + rt.dvEarthCaptureKms),
    aero: variant(rt.dvReturnDepartKms),
  };
}
