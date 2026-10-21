export const SAMPLE_TRIALS = Object.freeze([
  { force: 42.0, mass: 0.75, range: 55.0 },
  { force: 48.0, mass: 1.05, range: 50.0 },
  { force: 74.0, mass: 0.80, range: 105.0 },
  { force: 82.0, mass: 1.15, range: 98.0 },
  { force: 122.0, mass: 0.85, range: 195.0 },
  { force: 135.0, mass: 1.20, range: 205.0 },
  { force: 172.0, mass: 0.90, range: 295.0 },
  { force: 188.0, mass: 1.25, range: 305.0 },
]);

export function solve3x3(A, bVec) {
  const M = [
    [A[0][0], A[0][1], A[0][2], bVec[0]],
    [A[1][0], A[1][1], A[1][2], bVec[1]],
    [A[2][0], A[2][1], A[2][2], bVec[2]],
  ];

  for (let col = 0; col < 3; col++) {
    let pivotRow = col;
    for (let r = col + 1; r < 3; r++) {
      if (Math.abs(M[r][col]) > Math.abs(M[pivotRow][col])) {
        pivotRow = r;
      }
    }
    if (Math.abs(M[pivotRow][col]) < 1e-10) {
      return null;
    }
    const tmp = M[col];
    M[col] = M[pivotRow];
    M[pivotRow] = tmp;

    const pivot = M[col][col];
    for (let j = col; j < 4; j++) {
      M[col][j] /= pivot;
    }
    for (let r = 0; r < 3; r++) {
      if (r !== col) {
        const factor = M[r][col];
        for (let j = col; j < 4; j++) {
          M[r][j] -= factor * M[col][j];
        }
      }
    }
  }

  return [M[0][3], M[1][3], M[2][3]];
}

export function fitPlaneModel(dataPoints) {
  const n = dataPoints.length;
  if (n < 3) {
    return { coeffs: null, r2: null, rmse: null, reason: "MIN_POINTS" };
  }

  let sRR = 0;
  let sRM = 0;
  let sR = 0;
  let sMM = 0;
  let sM = 0;
  let sRF = 0;
  let sMF = 0;
  let sF = 0;

  for (let i = 0; i < n; i++) {
    const r = Number(dataPoints[i].range);
    const m = Number(dataPoints[i].mass);
    const f = Number(dataPoints[i].force);
    sRR += r * r;
    sRM += r * m;
    sR += r;
    sMM += m * m;
    sM += m;
    sRF += r * f;
    sMF += m * f;
    sF += f;
  }

  const xtx = [
    [sRR, sRM, sR],
    [sRM, sMM, sM],
    [sR, sM, n],
  ];
  const xty = [sRF, sMF, sF];

  const coeffs = solve3x3(xtx, xty);
  if (!coeffs) {
    return { coeffs: null, r2: null, rmse: null, reason: "COLLINEAR" };
  }

  const [a, b, c] = coeffs;
  const meanF = sF / n;
  let ssRes = 0;
  let ssTot = 0;

  for (let i = 0; i < n; i++) {
    const pt = dataPoints[i];
    const pred = a * pt.range + b * pt.mass + c;
    const res = pt.force - pred;
    ssRes += res * res;
    const diff = pt.force - meanF;
    ssTot += diff * diff;
  }

  const r2 = ssTot > 1e-12 ? 1.0 - ssRes / ssTot : 1.0;
  const rmse = Math.sqrt(ssRes / n);

  return { coeffs: { a, b, c }, r2, rmse, reason: "OK" };
}
