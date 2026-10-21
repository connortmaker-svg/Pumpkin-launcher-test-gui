// =============================================================================
// ELC PUMPKIN LAUNCHER 2026 - AERODYNAMIC & ELASTIC BAND PHYSICS MODULE
// =============================================================================

export const DEFAULT_CONSTANTS = Object.freeze({
  SLING_MASS: 1.5,
  BAND_STRENGTH: Number((4.4482 * ((14.3 + 21.3 / 2.0) / 2.0)).toFixed(4)),
  BAND_REST_LENGTH: 0.254,
  LAUNCH_ANGLE_DEG: 45.0,
  GRAVITY: 9.81,
  DRAG_COEFFICIENT: 0.55,
  AIR_DENSITY: 1.21,
  PUMPKIN_DENSITY: 800.0,
  NEWTON_TO_LBF: 0.2248,
});

export const DEFAULT_MATH_INPUTS = Object.freeze({
  pumpkin_mass: 0.9,
  efficiency: 0.8,
  band_count: 24,
  target_range: 300,
});

export function validateConstants(c) {
  if (!Number.isFinite(c.SLING_MASS) || c.SLING_MASS < 0) {
    throw new Error("Sling mass must be >= 0.");
  }
  if (!Number.isFinite(c.BAND_STRENGTH) || c.BAND_STRENGTH <= 0) {
    throw new Error("Band strength must be > 0.");
  }
  if (!Number.isFinite(c.BAND_REST_LENGTH) || c.BAND_REST_LENGTH <= 0) {
    throw new Error("Band rest length must be > 0.");
  }
  if (!Number.isFinite(c.LAUNCH_ANGLE_DEG) || c.LAUNCH_ANGLE_DEG <= 0 || c.LAUNCH_ANGLE_DEG >= 90) {
    throw new Error("Launch angle must be between 0 and 90 deg.");
  }
  if (
    !Number.isFinite(c.GRAVITY) || c.GRAVITY <= 0 ||
    !Number.isFinite(c.DRAG_COEFFICIENT) || c.DRAG_COEFFICIENT <= 0 ||
    !Number.isFinite(c.AIR_DENSITY) || c.AIR_DENSITY <= 0 ||
    !Number.isFinite(c.PUMPKIN_DENSITY) || c.PUMPKIN_DENSITY <= 0 ||
    !Number.isFinite(c.NEWTON_TO_LBF) || c.NEWTON_TO_LBF <= 0
  ) {
    throw new Error("Gravity, drag, densities, and conversion factor must be > 0.");
  }
}

export function evalPhysicsModel(inputs, constants) {
  const mass = Number(inputs.pumpkin_mass);
  const eff = Number(inputs.efficiency);
  const bands = Number(inputs.band_count);
  const targetFt = Number(inputs.target_range);

  if (!Number.isFinite(mass) || mass <= 0) {
    throw new Error("Pumpkin mass must be > 0 kg.");
  }
  if (!Number.isFinite(eff) || eff <= 0 || eff > 1.0) {
    throw new Error("Efficiency must be in (0, 1].");
  }
  if (!Number.isFinite(bands) || bands <= 0) {
    throw new Error("Band count must be > 0.");
  }
  if (!Number.isFinite(targetFt) || targetFt <= 0) {
    throw new Error("Target range must be > 0 ft.");
  }

  validateConstants(constants);

  const angleRad = (constants.LAUNCH_ANGLE_DEG * Math.PI) / 180.0;
  const sin2j = Math.sin(2.0 * angleRad);
  const sinJ = Math.sin(angleRad);

  const targetM = targetFt * 0.3048;
  const launchedMass = mass + constants.SLING_MASS;

  // Cross-sectional area of sphere: A = pi * r^2
  const radius = Math.cbrt((3.0 * (mass / constants.PUMPKIN_DENSITY)) / (4.0 * Math.PI));
  const area = Math.PI * radius * radius;

  // Drag velocity scale D
  const dragScale = Math.sqrt(
    (2.0 * mass * constants.GRAVITY) /
      (constants.AIR_DENSITY * area * constants.DRAG_COEFFICIENT)
  );

  // Vacuum velocity v_vac and initial velocity with quadratic drag v_0
  const rgSin2j = (targetM * constants.GRAVITY) / sin2j;
  const vVac = Math.sqrt(rgSin2j);
  const vInit = Math.sqrt(rgSin2j * (1.0 + (4.0 * vVac * sinJ) / (3.0 * dragScale)));

  // Band stiffness, elongation factor E_L, draw distance d, stretch ratio S_r
  const stiffness = (constants.BAND_STRENGTH * bands) / constants.BAND_REST_LENGTH;
  const elongation = Math.sqrt(launchedMass / (eff * stiffness));
  const drawDist = elongation * vInit;
  const stretchRatio = drawDist / constants.BAND_REST_LENGTH;

  // Launch force in Newtons and pounds-force
  const forceN = (launchedMass * vInit * vInit) / (eff * drawDist);
  const forceLbf = constants.NEWTON_TO_LBF * forceN;

  return {
    targetM,
    launchedMass,
    area,
    dragScale,
    vVac,
    vInit,
    stiffness,
    elongation,
    drawDist,
    stretchRatio,
    forceN,
    forceLbf,
    angleRad,
  };
}
