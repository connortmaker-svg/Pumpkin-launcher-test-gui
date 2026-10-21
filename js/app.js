import { DEFAULT_CONSTANTS, DEFAULT_MATH_INPUTS, evalPhysicsModel, validateConstants } from "./physics.js";
import { SAMPLE_TRIALS, fitPlaneModel } from "./regression.js";
import { Plot3DRenderer } from "./plot3d.js";
import {
  loadSavedState,
  saveStateToStorage,
  formatTrialsCSV,
  parseTrialsCSV,
  downloadTextFile,
  loadGitHubConfig,
  saveGitHubConfig,
  pullStateFromGitHub,
  pushStateToGitHub,
} from "./storage.js";

class PumpkinLauncherWebApp {
  constructor() {
    this.constants = { ...DEFAULT_CONSTANTS };
    this.dataPoints = SAMPLE_TRIALS.map((pt) => ({ ...pt }));
    this.selectedTrialIndices = new Set();
    this.planeCoeffs = null;
    this.ghConfig = loadGitHubConfig();
    this._ghAutoPushTimer = null;

    this._cacheDOM();
    this.plot3d = new Plot3DRenderer(this.el.canvasPlot);

    const hadLocalState = this._restoreState();
    this._syncGitHubInputsFromConfig();
    this._bindEvents();
    this._refreshConstantsSummary();
    this.recalcMathModel();
    this.refitPlane();

    if (!hadLocalState) {
      this.pullFromGitHub(true);
    }
  }

  _cacheDOM() {
    const $ = (id) => document.getElementById(id);
    this.el = {
      globalStatus: $("globalStatus"),
      tabBtns: Array.from(document.querySelectorAll(".tab-btn")),
      tabPanels: Array.from(document.querySelectorAll(".tab-panel")),

      mathMass: $("mathMass"),
      mathEff: $("mathEff"),
      mathBands: $("mathBands"),
      mathRange: $("mathRange"),
      mathPresetBtns: Array.from(document.querySelectorAll("[data-math-range]")),
      btnResetMath: $("btnResetMath"),
      btnGoSettings: $("btnGoSettings"),
      lblMathForceLbf: $("lblMathForceLbf"),
      lblMathForceSub: $("lblMathForceSub"),
      tbodyMathPresets: $("tbodyMathPresets"),
      tbodyConstantsSummary: $("tbodyConstantsSummary"),
      tbodyMathDetails: $("tbodyMathDetails"),

      trialForce: $("trialForce"),
      trialMass: $("trialMass"),
      trialRange: $("trialRange"),
      btnAddTrial: $("btnAddTrial"),
      tbodyTrials: $("tbodyTrials"),
      btnDeleteSelected: $("btnDeleteSelected"),
      btnClearTrials: $("btnClearTrials"),
      btnLoadSample: $("btnLoadSample"),
      btnPushGitHubQuick: $("btnPushGitHubQuick"),
      btnPullGitHubQuick: $("btnPullGitHubQuick"),
      btnExportCSV: $("btnExportCSV"),
      btnImportCSV: $("btnImportCSV"),
      fileInputCSV: $("fileInputCSV"),
      btnExportJSON: $("btnExportJSON"),
      btnImportJSON: $("btnImportJSON"),
      fileInputJSON: $("fileInputJSON"),
      lblPlaneEq: $("lblPlaneEq"),
      lblPlaneStats: $("lblPlaneStats"),
      predRange: $("predRange"),
      predMass: $("predMass"),
      predPresetBtns: Array.from(document.querySelectorAll("[data-pred-range]")),
      lblPredForceLbf: $("lblPredForceLbf"),
      lblPredForceSub: $("lblPredForceSub"),
      trPredAllTargets: $("trPredAllTargets"),
      canvasPlot: $("canvasPlot"),
      btnReset3DView: $("btnReset3DView"),

      ghRepo: $("ghRepo"),
      ghBranch: $("ghBranch"),
      ghToken: $("ghToken"),
      ghAutoSync: $("ghAutoSync"),
      lblGitHubSyncStatus: $("lblGitHubSyncStatus"),
      btnPullGitHub: $("btnPullGitHub"),
      btnPushGitHub: $("btnPushGitHub"),

      constSlingMass: $("constSlingMass"),
      constBandStrength: $("constBandStrength"),
      constBandRest: $("constBandRest"),
      constAngleDeg: $("constAngleDeg"),
      constGravity: $("constGravity"),
      constDrag: $("constDrag"),
      constAirRho: $("constAirRho"),
      constPumpkinRho: $("constPumpkinRho"),
      constNToLbf: $("constNToLbf"),
      lblSettingsStatus: $("lblSettingsStatus"),
      btnResetConstants: $("btnResetConstants"),
    };
  }

  _applyLoadedStateObject(saved) {
    if (!saved) return false;
    if (saved.math_inputs) {
      this.el.mathMass.value = saved.math_inputs.pumpkin_mass ?? DEFAULT_MATH_INPUTS.pumpkin_mass;
      this.el.mathEff.value = saved.math_inputs.efficiency ?? DEFAULT_MATH_INPUTS.efficiency;
      this.el.mathBands.value = saved.math_inputs.band_count ?? DEFAULT_MATH_INPUTS.band_count;
      this.el.mathRange.value = saved.math_inputs.target_range ?? DEFAULT_MATH_INPUTS.target_range;
    }
    if (saved.regression_inputs) {
      this.el.predRange.value = saved.regression_inputs.pred_range ?? 200;
      this.el.predMass.value = saved.regression_inputs.pred_mass ?? 0.9;
    }
    if (saved.constants) {
      this.constants = {
        SLING_MASS: Number(saved.constants.SLING_MASS ?? DEFAULT_CONSTANTS.SLING_MASS),
        BAND_STRENGTH: Number(saved.constants.BAND_STRENGTH ?? DEFAULT_CONSTANTS.BAND_STRENGTH),
        BAND_REST_LENGTH: Number(saved.constants.BAND_REST_LENGTH ?? DEFAULT_CONSTANTS.BAND_REST_LENGTH),
        LAUNCH_ANGLE_DEG: Number(saved.constants.LAUNCH_ANGLE_DEG ?? DEFAULT_CONSTANTS.LAUNCH_ANGLE_DEG),
        GRAVITY: Number(saved.constants.GRAVITY ?? DEFAULT_CONSTANTS.GRAVITY),
        DRAG_COEFFICIENT: Number(saved.constants.DRAG_COEFFICIENT ?? DEFAULT_CONSTANTS.DRAG_COEFFICIENT),
        AIR_DENSITY: Number(saved.constants.AIR_DENSITY ?? DEFAULT_CONSTANTS.AIR_DENSITY),
        PUMPKIN_DENSITY: Number(saved.constants.PUMPKIN_DENSITY ?? DEFAULT_CONSTANTS.PUMPKIN_DENSITY),
        NEWTON_TO_LBF: Number(saved.constants.NEWTON_TO_LBF ?? DEFAULT_CONSTANTS.NEWTON_TO_LBF),
      };
    }
    if (Array.isArray(saved.data_points) && saved.data_points.length > 0) {
      this.dataPoints = saved.data_points.map((pt) => ({
        force: Number(pt.force),
        mass: Number(pt.mass),
        range: Number(pt.range),
      }));
    }
    this._syncConstantsInputsFromState();
    return true;
  }

  _restoreState() {
    const saved = loadSavedState();
    const ok = this._applyLoadedStateObject(saved);
    this._syncConstantsInputsFromState();
    return ok;
  }

  _syncGitHubInputsFromConfig() {
    this.el.ghRepo.value = this.ghConfig.repo || "";
    this.el.ghBranch.value = this.ghConfig.branch || "main";
    this.el.ghToken.value = this.ghConfig.token || "";
    this.el.ghAutoSync.checked = Boolean(this.ghConfig.autoSync);
  }

  _readGitHubConfigFromInputs() {
    this.ghConfig = {
      repo: this.el.ghRepo.value.trim(),
      branch: this.el.ghBranch.value.trim() || "main",
      token: this.el.ghToken.value.trim(),
      autoSync: Boolean(this.el.ghAutoSync.checked),
    };
    saveGitHubConfig(this.ghConfig);
    return this.ghConfig;
  }

  _syncConstantsInputsFromState() {
    this.el.constSlingMass.value = this.constants.SLING_MASS;
    this.el.constBandStrength.value = this.constants.BAND_STRENGTH;
    this.el.constBandRest.value = this.constants.BAND_REST_LENGTH;
    this.el.constAngleDeg.value = this.constants.LAUNCH_ANGLE_DEG;
    this.el.constGravity.value = this.constants.GRAVITY;
    this.el.constDrag.value = this.constants.DRAG_COEFFICIENT;
    this.el.constAirRho.value = this.constants.AIR_DENSITY;
    this.el.constPumpkinRho.value = this.constants.PUMPKIN_DENSITY;
    this.el.constNToLbf.value = this.constants.NEWTON_TO_LBF;
  }

  _persistState(triggerGitHubAutoPush = false) {
    const state = {
      math_inputs: {
        pumpkin_mass: this.el.mathMass.value,
        efficiency: this.el.mathEff.value,
        band_count: this.el.mathBands.value,
        target_range: this.el.mathRange.value,
      },
      regression_inputs: {
        pred_range: this.el.predRange.value,
        pred_mass: this.el.predMass.value,
      },
      constants: { ...this.constants },
      data_points: this.dataPoints,
    };
    saveStateToStorage(state);

    if (triggerGitHubAutoPush && this.ghConfig.autoSync && this.ghConfig.token && this.ghConfig.repo) {
      if (this._ghAutoPushTimer) {
        clearTimeout(this._ghAutoPushTimer);
      }
      this._ghAutoPushTimer = setTimeout(() => {
        this.pushToGitHub(true);
      }, 1200);
    }

    return state;
  }

  async pullFromGitHub(silent = false) {
    const cfg = this._readGitHubConfigFromInputs();
    this.el.lblGitHubSyncStatus.className = "status-line muted";
    this.el.lblGitHubSyncStatus.textContent = "[SYNCING] PULLING DATA FROM GITHUB...";
    try {
      const remoteState = await pullStateFromGitHub(cfg);
      this._applyLoadedStateObject(remoteState);
      this.recalcMathModel();
      this.refitPlane();
      this.el.lblGitHubSyncStatus.className = "status-line";
      this.el.lblGitHubSyncStatus.textContent = `[OK] PULLED LATEST DATA FROM GITHUB (${this.dataPoints.length} TRIALS)`;
      this.el.globalStatus.textContent = "[SYNCED WITH GITHUB]";
    } catch (err) {
      this.el.lblGitHubSyncStatus.className = silent ? "status-line muted" : "status-line error";
      this.el.lblGitHubSyncStatus.textContent = silent
        ? "[OFFLINE / LOCAL MODE] USING DEVICE LOCAL STORAGE"
        : `[PULL ERROR] ${err.message}`;
      if (!silent) {
        window.alert(`Could not pull from GitHub:\n${err.message}`);
      }
    }
  }

  async pushToGitHub(silent = false) {
    const cfg = this._readGitHubConfigFromInputs();
    if (!cfg.token || !cfg.repo) {
      if (!silent) {
        this.switchTab("tabSettings");
        this.el.lblGitHubSyncStatus.className = "status-line error";
        this.el.lblGitHubSyncStatus.textContent =
          "[SETUP NEEDED] ENTER GITHUB REPO (OWNER/REPO) AND ACCESS TOKEN ABOVE TO COMMIT TO GITHUB";
        this.el.ghToken.focus();
      }
      return;
    }

    const state = this._persistState(false);
    this.el.lblGitHubSyncStatus.className = "status-line muted";
    this.el.lblGitHubSyncStatus.textContent = "[SYNCING] COMMITTING CSV & JSON TO GITHUB...";
    this.el.globalStatus.textContent = "[SAVING TO GITHUB...]";

    try {
      await pushStateToGitHub(cfg, state);
      this.el.lblGitHubSyncStatus.className = "status-line";
      this.el.lblGitHubSyncStatus.textContent = `[OK] COMMITTED pumpkin_launch_data.csv & launcher_state.json TO ${cfg.repo} (${cfg.branch})`;
      this.el.globalStatus.textContent = "[SAVED TO GITHUB]";
      if (!silent) {
        window.alert(`Saved pumpkin_launch_data.csv and launcher_state.json to GitHub (${cfg.repo}@${cfg.branch}).`);
      }
    } catch (err) {
      this.el.lblGitHubSyncStatus.className = "status-line error";
      this.el.lblGitHubSyncStatus.textContent = `[PUSH ERROR] ${err.message}`;
      this.el.globalStatus.textContent = "[SAVED LOCALLY ONLY]";
      if (!silent) {
        window.alert(`GitHub push failed:\n${err.message}`);
      }
    }
  }

  switchTab(tabId) {
    for (const btn of this.el.tabBtns) {
      btn.classList.toggle("active", btn.dataset.tab === tabId);
    }
    for (const panel of this.el.tabPanels) {
      panel.classList.toggle("active", panel.id === tabId);
    }
    if (tabId === "tabRegression") {
      this.plot3d.requestRender();
    }
  }

  _bindEvents() {
    for (const btn of this.el.tabBtns) {
      btn.addEventListener("click", () => this.switchTab(btn.dataset.tab));
    }

    for (const input of [this.el.mathMass, this.el.mathEff, this.el.mathBands, this.el.mathRange]) {
      input.addEventListener("input", () => this.recalcMathModel());
    }
    for (const btn of this.el.mathPresetBtns) {
      btn.addEventListener("click", () => {
        this.el.mathRange.value = btn.dataset.mathRange;
        this.recalcMathModel();
      });
    }
    this.el.btnResetMath.addEventListener("click", () => {
      this.el.mathMass.value = DEFAULT_MATH_INPUTS.pumpkin_mass;
      this.el.mathEff.value = DEFAULT_MATH_INPUTS.efficiency;
      this.el.mathBands.value = DEFAULT_MATH_INPUTS.band_count;
      this.el.mathRange.value = DEFAULT_MATH_INPUTS.target_range;
      this.recalcMathModel();
    });
    this.el.btnGoSettings.addEventListener("click", () => this.switchTab("tabSettings"));

    this.el.btnAddTrial.addEventListener("click", () => this.addTrialPoint());
    for (const inp of [this.el.trialForce, this.el.trialMass, this.el.trialRange]) {
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          this.addTrialPoint();
        }
      });
    }

    this.el.btnDeleteSelected.addEventListener("click", () => this.deleteSelectedTrials());
    this.el.btnClearTrials.addEventListener("click", () => {
      if (this.dataPoints.length === 0) return;
      if (window.confirm("Remove all recorded launch trials?")) {
        this.dataPoints = [];
        this.selectedTrialIndices.clear();
        this.refitPlane(true);
      }
    });
    this.el.btnLoadSample.addEventListener("click", () => {
      this.dataPoints = SAMPLE_TRIALS.map((pt) => ({ ...pt }));
      this.selectedTrialIndices.clear();
      this.refitPlane(true);
    });

    this.el.btnPushGitHubQuick.addEventListener("click", () => this.pushToGitHub(false));
    this.el.btnPullGitHubQuick.addEventListener("click", () => this.pullFromGitHub(false));

    this.el.btnExportCSV.addEventListener("click", () => {
      if (this.dataPoints.length === 0) return;
      const csvText = formatTrialsCSV(this.dataPoints);
      downloadTextFile("pumpkin_launch_data.csv", csvText, "text/csv;charset=utf-8");
    });
    this.el.btnImportCSV.addEventListener("click", () => this.el.fileInputCSV.click());
    this.el.fileInputCSV.addEventListener("change", (e) => this._handleCSVImport(e));

    this.el.btnExportJSON.addEventListener("click", () => {
      const state = this._persistState(false);
      downloadTextFile("launcher_state.json", JSON.stringify(state, null, 2), "application/json;charset=utf-8");
    });
    this.el.btnImportJSON.addEventListener("click", () => this.el.fileInputJSON.click());
    this.el.fileInputJSON.addEventListener("change", (e) => this._handleJSONImport(e));

    for (const btn of this.el.predPresetBtns) {
      btn.addEventListener("click", () => {
        this.el.predRange.value = btn.dataset.predRange;
        this.updatePlanePrediction();
      });
    }
    this.el.predRange.addEventListener("input", () => this.updatePlanePrediction());
    this.el.predMass.addEventListener("input", () => this.updatePlanePrediction());
    this.el.btnReset3DView.addEventListener("click", () => this.plot3d.resetView());

    for (const ghInp of [this.el.ghRepo, this.el.ghBranch, this.el.ghToken, this.el.ghAutoSync]) {
      ghInp.addEventListener("input", () => this._readGitHubConfigFromInputs());
      ghInp.addEventListener("change", () => this._readGitHubConfigFromInputs());
    }
    this.el.btnPullGitHub.addEventListener("click", () => this.pullFromGitHub(false));
    this.el.btnPushGitHub.addEventListener("click", () => this.pushToGitHub(false));

    const constInputs = [
      this.el.constSlingMass,
      this.el.constBandStrength,
      this.el.constBandRest,
      this.el.constAngleDeg,
      this.el.constGravity,
      this.el.constDrag,
      this.el.constAirRho,
      this.el.constPumpkinRho,
      this.el.constNToLbf,
    ];
    for (const inp of constInputs) {
      inp.addEventListener("input", () => this.onConstantsEdited());
    }
    this.el.btnResetConstants.addEventListener("click", () => {
      this.constants = { ...DEFAULT_CONSTANTS };
      this._syncConstantsInputsFromState();
      this.onConstantsEdited();
    });
  }

  _refreshConstantsSummary() {
    const c = this.constants;
    const rad = ((c.LAUNCH_ANGLE_DEG * Math.PI) / 180.0).toFixed(4);
    const rows = [
      ["SLING MASS (m_s)", `${c.SLING_MASS} kg`],
      ["BAND STRENGTH (S)", `${Number(c.BAND_STRENGTH).toFixed(4)} N`],
      ["BAND REST LEN (L_0)", `${c.BAND_REST_LENGTH} m`],
      ["LAUNCH ANGLE (j)", `${c.LAUNCH_ANGLE_DEG} deg (${rad} rad)`],
      ["GRAVITY (g)", `${c.GRAVITY} m/s^2`],
      ["DRAG COEFF (c)", `${c.DRAG_COEFFICIENT}`],
      ["AIR DENSITY (p)", `${c.AIR_DENSITY} kg/m^3`],
      ["PUMPKIN DENSITY", `${c.PUMPKIN_DENSITY} kg/m^3`],
      ["N TO LBF FACTOR", `${c.NEWTON_TO_LBF} lbf/N`],
    ];
    this.el.tbodyConstantsSummary.innerHTML = rows
      .map((r) => `<tr><td class="kv-key">${r[0]}</td><td class="kv-val">${r[1]}</td></tr>`)
      .join("");
  }

  recalcMathModel() {
    this._refreshConstantsSummary();
    const curRange = Number(this.el.mathRange.value);
    for (const btn of this.el.mathPresetBtns) {
      btn.classList.toggle("active-preset", Number(btn.dataset.mathRange) === curRange);
    }

    try {
      const inputs = {
        pumpkin_mass: this.el.mathMass.value,
        efficiency: this.el.mathEff.value,
        band_count: this.el.mathBands.value,
        target_range: this.el.mathRange.value,
      };
      const res = evalPhysicsModel(inputs, this.constants);

      this.el.lblMathForceLbf.textContent = `${res.forceLbf.toFixed(2)} LBF`;
      this.el.lblMathForceSub.className = "status-line";
      this.el.lblMathForceSub.textContent = `[OK] ${res.forceN.toFixed(2)} N  |  DRAW d = ${res.drawDist.toFixed(3)} M  |  STRETCH S_r = ${res.stretchRatio.toFixed(2)}`;
      this.el.globalStatus.textContent = "[OFFLINE AUTO-SAVED]";

      const details = [
        ["TARGET RANGE 0.3048*R (M)", `${res.targetM.toFixed(4)} m`],
        ["TOTAL MASS m_total = m_p + m_s (KG)", `${res.launchedMass.toFixed(4)} kg`],
        ["CROSS-SECTIONAL AREA A (M^2)", `${res.area.toFixed(6)} m^2`],
        ["DRAG VELOCITY SCALE D (M/S)", `${res.dragScale.toFixed(4)} m/s`],
        ["VACUUM VELOCITY v_vac (M/S)", `${res.vVac.toFixed(4)} m/s`],
        ["INITIAL VELOCITY v_0 (M/S)", `${res.vInit.toFixed(4)} m/s`],
        ["BAND STIFFNESS S*B/L_0 (N/M)", `${res.stiffness.toFixed(2)} N/m`],
        ["ELONGATION FACTOR E_L (S)", `${res.elongation.toFixed(6)} s`],
        ["DRAW DISTANCE d = E_L * v_0 (M)", `${res.drawDist.toFixed(4)} m`],
        ["STRETCH RATIO S_r = d / L_0", `${res.stretchRatio.toFixed(4)}`],
      ];
      this.el.tbodyMathDetails.innerHTML = details
        .map((d) => `<tr><td class="kv-key">${d[0]}</td><td class="kv-val">${d[1]}</td></tr>`)
        .join("");

      const presetRows = [50, 100, 200, 300].map((rFt) => {
        const rRes = evalPhysicsModel({ ...inputs, target_range: rFt }, this.constants);
        return `<tr>
          <td>${rFt} ft</td>
          <td>${rRes.vVac.toFixed(2)}</td>
          <td>${rRes.vInit.toFixed(2)}</td>
          <td>${rRes.drawDist.toFixed(3)}</td>
          <td>${rRes.stretchRatio.toFixed(2)}</td>
          <td>${rRes.forceLbf.toFixed(2)} lbf</td>
          <td>${rRes.forceN.toFixed(1)} N</td>
        </tr>`;
      });
      this.el.tbodyMathPresets.innerHTML = presetRows.join("");

      this._persistState(false);
    } catch (err) {
      this.el.lblMathForceLbf.textContent = "-- LBF";
      this.el.lblMathForceSub.className = "status-line error";
      this.el.lblMathForceSub.textContent = `[INPUT PENDING] ${err.message}`;
      this.el.globalStatus.textContent = "[CHECK INPUT]";
    }
  }

  onConstantsEdited() {
    try {
      const candidate = {
        SLING_MASS: Number(this.el.constSlingMass.value),
        BAND_STRENGTH: Number(this.el.constBandStrength.value),
        BAND_REST_LENGTH: Number(this.el.constBandRest.value),
        LAUNCH_ANGLE_DEG: Number(this.el.constAngleDeg.value),
        GRAVITY: Number(this.el.constGravity.value),
        DRAG_COEFFICIENT: Number(this.el.constDrag.value),
        AIR_DENSITY: Number(this.el.constAirRho.value),
        PUMPKIN_DENSITY: Number(this.el.constPumpkinRho.value),
        NEWTON_TO_LBF: Number(this.el.constNToLbf.value),
      };
      validateConstants(candidate);
      this.constants = candidate;

      this.el.lblSettingsStatus.className = "status-line";
      this.el.lblSettingsStatus.textContent = "[OK] CONSTANTS UPDATED AND SAVED AUTOMATICALLY";

      this.recalcMathModel();
      this.updatePlanePrediction();
      this._persistState(true);
    } catch (err) {
      this.el.lblSettingsStatus.className = "status-line error";
      this.el.lblSettingsStatus.textContent = `[INVALID CONSTANT] ${err.message}`;
    }
  }

  addTrialPoint() {
    const force = Number(this.el.trialForce.value);
    const mass = Number(this.el.trialMass.value);
    const range = Number(this.el.trialRange.value);

    if (!Number.isFinite(force) || !Number.isFinite(mass) || !Number.isFinite(range) || force <= 0 || mass <= 0 || range <= 0) {
      window.alert("Enter positive numbers for Force (lbf), Mass (kg), and Range (ft).");
      return;
    }

    this.dataPoints.push({ force, mass, range });
    this.el.trialForce.value = "";
    this.el.trialMass.value = "";
    this.el.trialRange.value = "";
    this.refitPlane(true);
  }

  deleteSelectedTrials() {
    if (this.selectedTrialIndices.size === 0) return;
    this.dataPoints = this.dataPoints.filter((_, idx) => !this.selectedTrialIndices.has(idx));
    this.selectedTrialIndices.clear();
    this.refitPlane(true);
  }

  refitPlane(triggerGitHubAutoPush = false) {
    const fit = fitPlaneModel(this.dataPoints);
    this.planeCoeffs = fit.coeffs;

    this.el.tbodyTrials.innerHTML = this.dataPoints
      .map((pt, idx) => {
        let predStr = "--";
        let residStr = "--";
        if (this.planeCoeffs) {
          const { a, b, c } = this.planeCoeffs;
          const pred = a * pt.range + b * pt.mass + c;
          const resid = pt.force - pred;
          predStr = pred.toFixed(2);
          residStr = (resid >= 0 ? "+" : "") + resid.toFixed(2);
        }
        const selectedClass = this.selectedTrialIndices.has(idx) ? "selected-row" : "";
        return `<tr class="clickable-row ${selectedClass}" data-idx="${idx}">
          <td>${idx + 1}</td>
          <td>${pt.force.toFixed(2)}</td>
          <td>${pt.mass.toFixed(3)}</td>
          <td>${pt.range.toFixed(1)}</td>
          <td>${predStr}</td>
          <td>${residStr}</td>
        </tr>`;
      })
      .join("");

    const rows = this.el.tbodyTrials.querySelectorAll("tr.clickable-row");
    for (const row of rows) {
      row.addEventListener("click", () => {
        const idx = Number(row.dataset.idx);
        if (this.selectedTrialIndices.has(idx)) {
          this.selectedTrialIndices.delete(idx);
          row.classList.remove("selected-row");
        } else {
          this.selectedTrialIndices.add(idx);
          row.classList.add("selected-row");
        }
      });
    }

    if (this.planeCoeffs) {
      const { a, b, c } = this.planeCoeffs;
      const signB = b >= 0 ? "+" : "-";
      const signC = c >= 0 ? "+" : "-";
      this.el.lblPlaneEq.textContent = `FORCE = ${a.toFixed(4)}*RANGE ${signB} ${Math.abs(b).toFixed(4)}*MASS ${signC} ${Math.abs(c).toFixed(4)}`;
      this.el.lblPlaneStats.className = "status-line";
      this.el.lblPlaneStats.textContent = `[FIT OK] N = ${this.dataPoints.length}  |  R^2 = ${fit.r2.toFixed(4)}  |  RMSE = ${fit.rmse.toFixed(2)} LBF`;
    } else {
      if (fit.reason === "MIN_POINTS") {
        this.el.lblPlaneEq.textContent = `[PENDING] MINIMUM 3 POINTS REQUIRED (CURRENT: ${this.dataPoints.length})`;
      } else {
        this.el.lblPlaneEq.textContent = "[ERROR] POINTS ARE COLLINEAR. ADD VARIED MASS AND RANGE DATA.";
      }
      this.el.lblPlaneStats.className = "status-line muted";
      this.el.lblPlaneStats.textContent = "R^2 = --  |  RMSE = --";
    }

    this.updatePlanePrediction();
    this._persistState(triggerGitHubAutoPush);
  }

  updatePlanePrediction() {
    const targetRange = Number(this.el.predRange.value);
    const mass = Number(this.el.predMass.value);

    for (const btn of this.el.predPresetBtns) {
      btn.classList.toggle("active-preset", Number(btn.dataset.predRange) === targetRange);
    }

    if (!this.planeCoeffs) {
      this.el.lblPredForceLbf.textContent = "-- LBF";
      this.el.lblPredForceSub.className = "status-line error";
      this.el.lblPredForceSub.textContent = "[WAITING] Fit plane with at least 3 non-collinear points.";
      this.el.trPredAllTargets.innerHTML = "<td>--</td><td>--</td><td>--</td><td>--</td>";
      this.plot3d.updateState({
        dataPoints: this.dataPoints,
        coeffs: null,
        targetRange,
        targetMass: mass,
      });
      return;
    }

    if (!Number.isFinite(targetRange) || !Number.isFinite(mass) || targetRange <= 0 || mass <= 0) {
      this.el.lblPredForceLbf.textContent = "-- LBF";
      this.el.lblPredForceSub.className = "status-line error";
      this.el.lblPredForceSub.textContent = "[INPUT PENDING] Target range and pumpkin mass must be > 0.";
      this.el.trPredAllTargets.innerHTML = "<td>--</td><td>--</td><td>--</td><td>--</td>";
      return;
    }

    const { a, b, c } = this.planeCoeffs;
    const neededForce = a * targetRange + b * mass + c;
    const neededForceN = neededForce / this.constants.NEWTON_TO_LBF;

    this.el.lblPredForceLbf.textContent = `${neededForce.toFixed(2)} LBF`;
    this.el.lblPredForceSub.className = "status-line";
    this.el.lblPredForceSub.textContent = `[OK] ${neededForceN.toFixed(1)} N  |  TARGET RANGE: ${targetRange} FT  |  MASS: ${mass} KG`;

    this.el.trPredAllTargets.innerHTML = [50, 100, 200, 300]
      .map((rFt) => `<td>${(a * rFt + b * mass + c).toFixed(2)} LBF</td>`)
      .join("");

    this.plot3d.updateState({
      dataPoints: this.dataPoints,
      coeffs: this.planeCoeffs,
      targetRange,
      targetMass: mass,
    });

    this._persistState(false);
  }

  _handleCSVImport(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const parsed = parseTrialsCSV(String(reader.result || ""));
      if (parsed.length === 0) {
        window.alert("No valid (Force, Mass, Range) rows found in CSV.");
        return;
      }
      this.dataPoints = parsed;
      this.selectedTrialIndices.clear();
      this.refitPlane(true);
    };
    reader.readAsText(file);
    event.target.value = "";
  }

  _handleJSONImport(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const state = JSON.parse(String(reader.result || "{}"));
        saveStateToStorage(state);
        this._restoreState();
        this.recalcMathModel();
        this.refitPlane(true);
      } catch (err) {
        window.alert(`Invalid JSON state file: ${err.message}`);
      }
    };
    reader.readAsText(file);
    event.target.value = "";
  }
}

window.addEventListener("DOMContentLoaded", () => {
  new PumpkinLauncherWebApp();

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
});
