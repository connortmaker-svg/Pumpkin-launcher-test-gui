const PALETTE = Object.freeze({
  bg: "#222222",
  gold: "#D4A329",
  white: "#F5F5F5",
  muted: "#B5B5B5",
  borderDark: "#3D3D3D",
  borderMid: "#5A5A5A",
  green: "#38D952",
  darkOutline: "#1A1A1A",
});

export class Plot3DRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");

    this.camAzim = (-52.0 * Math.PI) / 180.0;
    this.camElev = (24.0 * Math.PI) / 180.0;

    this._dragging = false;
    this._lastX = 0;
    this._lastY = 0;
    this._rafPending = false;

    this.state = {
      dataPoints: [],
      coeffs: null,
      targetRange: 200,
      targetMass: 0.9,
    };

    this._bindEvents();
  }

  _bindEvents() {
    this.canvas.addEventListener("pointerdown", (e) => {
      this._dragging = true;
      this._lastX = e.clientX;
      this._lastY = e.clientY;
      try {
        this.canvas.setPointerCapture(e.pointerId);
      } catch (_err) {}
    });

    this.canvas.addEventListener("pointermove", (e) => {
      if (!this._dragging) return;
      const dx = e.clientX - this._lastX;
      const dy = e.clientY - this._lastY;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;

      this._lastX = e.clientX;
      this._lastY = e.clientY;

      this.camAzim += dx * 0.012;
      const minElev = (5.0 * Math.PI) / 180.0;
      const maxElev = (80.0 * Math.PI) / 180.0;
      this.camElev = Math.max(minElev, Math.min(maxElev, this.camElev + dy * 0.012));

      this.requestRender();
    });

    const stopDrag = () => {
      this._dragging = false;
    };
    this.canvas.addEventListener("pointerup", stopDrag);
    this.canvas.addEventListener("pointercancel", stopDrag);

    window.addEventListener("resize", () => this.requestRender());
  }

  resetView() {
    this.camAzim = (-52.0 * Math.PI) / 180.0;
    this.camElev = (24.0 * Math.PI) / 180.0;
    this.requestRender();
  }

  updateState(partialState) {
    Object.assign(this.state, partialState);
    this.requestRender();
  }

  requestRender() {
    if (this._rafPending) return;
    this._rafPending = true;
    requestAnimationFrame(() => {
      this._rafPending = false;
      this.render();
    });
  }

  render() {
    const rect = this.canvas.getBoundingClientRect();
    const w = rect.width;
    const h = rect.height;
    if (w < 80 || h < 80) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const targetW = Math.round(w * dpr);
    const targetH = Math.round(h * dpr);
    if (this.canvas.width !== targetW || this.canvas.height !== targetH) {
      this.canvas.width = targetW;
      this.canvas.height = targetH;
    }

    const ctx = this.ctx;
    ctx.save();
    ctx.scale(dpr, dpr);

    ctx.fillStyle = PALETTE.bg;
    ctx.fillRect(0, 0, w, h);

    const { dataPoints, coeffs, targetRange, targetMass } = this.state;

    let rMin = 0.0;
    let rMax = 320.0;
    let mMin = 0.4;
    let mMax = 1.5;
    let fMin = 0.0;
    let fMax = 220.0;

    for (let i = 0; i < dataPoints.length; i++) {
      const pt = dataPoints[i];
      rMax = Math.max(rMax, pt.range * 1.08);
      mMin = Math.min(mMin, pt.mass * 0.85);
      mMax = Math.max(mMax, pt.mass * 1.12);
      fMax = Math.max(fMax, pt.force * 1.15);
    }

    const userR = Number(targetRange) > 0 ? Number(targetRange) : 200.0;
    const userM = Number(targetMass) > 0 ? Number(targetMass) : 0.9;
    rMax = Math.max(rMax, userR * 1.08);
    mMin = Math.min(mMin, userM * 0.85);
    mMax = Math.max(mMax, userM * 1.12);

    if (coeffs) {
      const { a, b, c } = coeffs;
      const corners = [
        a * rMin + b * mMin + c,
        a * rMax + b * mMin + c,
        a * rMin + b * mMax + c,
        a * rMax + b * mMax + c,
      ];
      fMax = Math.max(fMax, Math.max(...corners) * 1.1, 50.0);
      fMin = Math.min(0.0, Math.min(...corners));
    }

    const rSpan = Math.max(1e-6, rMax - rMin);
    const mSpan = Math.max(1e-6, mMax - mMin);
    const fSpan = Math.max(1e-6, fMax - fMin);

    const invRSpan = 2.0 / rSpan;
    const invMSpan = 2.0 / mSpan;
    const invFSpan = 2.0 / fSpan;

    const cx = w * 0.5;
    const cy = h * 0.54;
    const scale = Math.min(w, h) * 0.36;

    const cosA = Math.cos(this.camAzim) * scale;
    const sinA = Math.sin(this.camAzim) * scale;
    const cosE = Math.cos(this.camElev) * scale;
    const sinE = Math.sin(this.camElev) * scale;

    const project = (rVal, mVal, fVal) => {
      const nx = (rVal - rMin) * invRSpan - 1.0;
      const ny = (mVal - mMin) * invMSpan - 1.0;
      const nz = (fVal - fMin) * invFSpan - 1.0;

      const sx = nx * cosA - ny * sinA;
      const ryScaled = nx * sinA + ny * cosA;
      const sy = -nz * cosE + ryScaled * sinE;
      return [cx + sx, cy + sy];
    };

    const drawLine = (p1, p2, color, width = 1, dash = []) => {
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.setLineDash(dash);
      ctx.moveTo(p1[0], p1[1]);
      ctx.lineTo(p2[0], p2[1]);
      ctx.stroke();
    };

    const boxBottom = [
      project(rMin, mMin, fMin),
      project(rMax, mMin, fMin),
      project(rMax, mMax, fMin),
      project(rMin, mMax, fMin),
    ];
    const boxTop = [
      project(rMin, mMin, fMax),
      project(rMax, mMin, fMax),
      project(rMax, mMax, fMax),
      project(rMin, mMax, fMax),
    ];

    ctx.font = 'bold 11px "Courier New", Courier, monospace';
    ctx.fillStyle = PALETTE.muted;

    for (const rTick of [50, 100, 200, 300]) {
      if (rTick >= rMin && rTick <= rMax) {
        const p1 = project(rTick, mMin, fMin);
        const p2 = project(rTick, mMax, fMin);
        drawLine(p1, p2, PALETTE.borderDark, 1, [2, 3]);
        ctx.textAlign = "center";
        ctx.fillText(`${rTick}FT`, p1[0], p1[1] + 13);
      }
    }

    const mSteps = 3;
    for (let i = 0; i <= mSteps; i++) {
      const mTick = mMin + (mSpan * i) / mSteps;
      const p1 = project(rMin, mTick, fMin);
      const p2 = project(rMax, mTick, fMin);
      drawLine(p1, p2, PALETTE.borderDark, 1, [2, 3]);
      ctx.textAlign = "left";
      ctx.fillText(`${mTick.toFixed(2)}KG`, p2[0] + 6, p2[1] + 4);
    }

    const zSteps = 4;
    for (let i = 0; i <= zSteps; i++) {
      const fTick = fMin + (fSpan * i) / zSteps;
      const pz = project(rMin, mMin, fTick);
      const pzEnd = project(rMax, mMin, fTick);
      drawLine(pz, pzEnd, PALETTE.borderDark, 1, [1, 4]);
      ctx.textAlign = "right";
      ctx.fillText(`${Math.round(fTick)}`, pz[0] - 8, pz[1] + 4);
    }

    for (let i = 0; i < 4; i++) {
      drawLine(boxBottom[i], boxBottom[(i + 1) % 4], PALETTE.borderMid, 1);
      drawLine(boxTop[i], boxTop[(i + 1) % 4], PALETTE.borderDark, 1);
      drawLine(boxBottom[i], boxTop[i], PALETTE.borderDark, 1);
    }

    const origin = boxBottom[0];
    const axR = boxBottom[1];
    const axM = boxBottom[3];
    const axF = boxTop[0];

    drawLine(origin, axR, PALETTE.gold, 2);
    drawLine(origin, axM, PALETTE.gold, 2);
    drawLine(origin, axF, PALETTE.gold, 2);

    ctx.fillStyle = PALETTE.gold;
    ctx.font = 'bold 12px "Courier New", Courier, monospace';
    ctx.textAlign = "center";
    ctx.fillText("X: RANGE (FT)", (origin[0] + axR[0]) * 0.5, (origin[1] + axR[1]) * 0.5 + 26);
    ctx.fillText("Y: MASS (KG)", axM[0] - 10, axM[1] + 18);
    ctx.fillText("Z: FORCE (LBF)", axF[0], axF[1] - 10);

    if (coeffs) {
      const { a, b, c } = coeffs;
      const gridR = 6;
      const gridM = 4;

      for (let j = 0; j <= gridM; j++) {
        const mVal = mMin + (mSpan * j) / gridM;
        const pStart = project(rMin, mVal, a * rMin + b * mVal + c);
        const pEnd = project(rMax, mVal, a * rMax + b * mVal + c);
        const col = j === 0 || j === gridM ? PALETTE.gold : PALETTE.borderMid;
        drawLine(pStart, pEnd, col, 1);
      }

      for (let i = 0; i <= gridR; i++) {
        const rVal = rMin + (rSpan * i) / gridR;
        const pStart = project(rVal, mMin, a * rVal + b * mMin + c);
        const pEnd = project(rVal, mMax, a * rVal + b * mMax + c);
        const col = i === 0 || i === gridR ? PALETTE.gold : PALETTE.borderMid;
        drawLine(pStart, pEnd, col, 1);
      }

      for (const rStd of [50, 100, 200, 300]) {
        if (rStd >= rMin && rStd <= rMax) {
          const pStart = project(rStd, mMin, a * rStd + b * mMin + c);
          const pEnd = project(rStd, mMax, a * rStd + b * mMax + c);
          drawLine(pStart, pEnd, PALETTE.gold, 2, [4, 2]);
        }
      }
    }

    ctx.setLineDash([]);
    for (let i = 0; i < dataPoints.length; i++) {
      const pt = dataPoints[i];
      const [px, py] = project(pt.range, pt.mass, pt.force);
      if (coeffs) {
        const { a, b, c } = coeffs;
        const fHat = a * pt.range + b * pt.mass + c;
        const [hx, hy] = project(pt.range, pt.mass, fHat);
        drawLine([px, py], [hx, hy], PALETTE.muted, 1, [2, 2]);
        ctx.setLineDash([]);
        ctx.fillStyle = PALETTE.gold;
        ctx.fillRect(hx - 2, hy - 2, 4, 4);
      }

      ctx.fillStyle = PALETTE.white;
      ctx.strokeStyle = PALETTE.gold;
      ctx.lineWidth = 1;
      ctx.fillRect(px - 4, py - 4, 8, 8);
      ctx.strokeRect(px - 4, py - 4, 8, 8);
    }

    if (coeffs && Number(targetRange) > 0 && Number(targetMass) > 0) {
      const { a, b, c } = coeffs;
      const predF = a * Number(targetRange) + b * Number(targetMass) + c;
      const [tx, ty] = project(Number(targetRange), Number(targetMass), predF);
      const [fx, fy] = project(Number(targetRange), Number(targetMass), fMin);

      drawLine([tx, ty], [fx, fy], PALETTE.green, 2, [3, 3]);
      ctx.setLineDash([]);
      ctx.fillStyle = PALETTE.green;
      ctx.strokeStyle = PALETTE.darkOutline;
      ctx.lineWidth = 1;
      ctx.fillRect(tx - 6, ty - 6, 12, 12);
      ctx.strokeRect(tx - 6, ty - 6, 12, 12);

      ctx.textAlign = "left";
      ctx.font = 'bold 12px "Courier New", Courier, monospace';
      ctx.fillText(
        `[${Number(targetRange)}FT, ${Number(targetMass)}KG -> ${predF.toFixed(1)}LBF]`,
        tx + 10,
        ty - 8
      );
    }

    ctx.restore();
  }
}
