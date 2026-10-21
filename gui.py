import csv
import json
import math
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV_PATH = os.path.join(APP_DIR, "pumpkin_launch_data.csv")
DEFAULT_JSON_PATH = os.path.join(APP_DIR, "launcher_state.json")

try:
    import equation_solver as es
except ImportError:
    # Built-in offline fallback so gui.py also works as a standalone single file on a Raspberry Pi
    class _FallbackSolver:
        SLING_MASS = 1.5
        BAND_STRENGTH = 4.4482 * ((14.3 + (21.3 / 2.0)) / 2.0)
        BAND_REST_LENGTH = 0.254
        LAUNCH_ANGLE = math.radians(45.0)
        GRAVITY = 9.81
        DRAG_COEFFICIENT = 0.55
        AIR_DENSITY = 1.21
        PUMPKIN_DENSITY = 800.0
        pumpkin_mass = 0.9
        efficiency = 0.8
        band_count = 24
        target_range = 300.0
        newton_to_pound_force = 0.2248
        target_range_converted = 300.0 * 0.3048

    es = _FallbackSolver()

# =============================================================================
# ELC GUI THEME PALETTE (Softer Dark Surfaces, Higher Visibility, Less Glare)
# =============================================================================
BG_MAIN = "#1A1A1A"
SURFACE_1 = "#222222"
SURFACE_2 = "#2A2A2A"
SURFACE_3 = "#333333"
MCC_GOLD = "#D4A329"
HOVER_GOLD = "#E5B842"
TEXT_WHITE = "#F5F5F5"
TEXT_BODY = "#EAEAEA"
TEXT_MUTED = "#B5B5B5"
TEXT_DISABLED = "#777777"
BORDER_DARK = "#3D3D3D"
BORDER_MID = "#5A5A5A"
ERROR_RED = "#FF5555"
SUCCESS_GREEN = "#38D952"

# Use native fast monospace font per OS to avoid X11/fontconfig lookup stalls on Raspberry Pi
FONT_FAMILY = "Courier New" if sys.platform.startswith("win") else "Courier"

# Pre-allocated font tuples to avoid repeated Tcl font object allocations
FONT_BODY = (FONT_FAMILY, 12)
FONT_BOLD = (FONT_FAMILY, 12, "bold")
FONT_HEADER = (FONT_FAMILY, 22, "bold")
FONT_MICRO = (FONT_FAMILY, 11, "bold")
FONT_MUTED = (FONT_FAMILY, 11)
FONT_ENTRY = (FONT_FAMILY, 13, "bold")
FONT_EQ = (FONT_FAMILY, 13, "bold")
FONT_HUGE = (FONT_FAMILY, 46, "bold")
FONT_PLOT_SM = (FONT_FAMILY, 9, "bold")
FONT_PLOT_MD = (FONT_FAMILY, 10, "bold")

DEFAULT_CONSTANTS = {
    "SLING_MASS": 1.5,
    "BAND_STRENGTH": 4.4482 * ((14.3 + (21.3 / 2.0)) / 2.0),
    "BAND_REST_LENGTH": 0.254,
    "LAUNCH_ANGLE_DEG": 45.0,
    "GRAVITY": 9.81,
    "DRAG_COEFFICIENT": 0.55,
    "AIR_DENSITY": 1.21,
    "PUMPKIN_DENSITY": 800.0,
    "NEWTON_TO_LBF": 0.2248,
}


class PumpkinLauncherGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        # Withdraw during initial widget tree construction for instant startup on X11 / Raspberry Pi
        self.root.withdraw()
        self.root.title("ELC PUMPKIN LAUNCHER 2026 - FORCE CALCULATOR (OFFLINE)")
        self.root.geometry("1240x840")
        self.root.minsize(980, 700)
        self.root.configure(bg=BG_MAIN)

        self.data_points = []
        self.plane_coeffs = None
        self._suppress_trace = False

        # Coalesced timer IDs for low-CPU hardware responsiveness
        self._math_calc_job = None
        self._const_calc_job = None
        self._pred_calc_job = None
        self._plot_redraw_job = None
        self._save_state_job = None

        # 3D Plot camera angles (radians) and drag state
        self.cam_azim = math.radians(-52.0)
        self.cam_elev = math.radians(24.0)
        self._drag_last = None

        self._apply_styles()
        self._build_top_bar()
        self._build_notebook()

        self._load_persisted_data()
        self.calculate_math_model()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Map window once all widgets are ready
        self.root.deiconify()

    def _on_close(self):
        self._save_state_now()
        self.root.destroy()

    def _schedule_save_state(self):
        if self._suppress_trace:
            return
        if self._save_state_job is not None:
            self.root.after_cancel(self._save_state_job)
        self._save_state_job = self.root.after(250, self._save_state_now)

    def _save_trials_csv(self, csv_path: str = DEFAULT_CSV_PATH):
        try:
            with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Force_lbf", "Pumpkin_Mass_kg", "Launch_Range_ft"])
                for pt in self.data_points:
                    writer.writerow([pt["force"], pt["mass"], pt["range"]])
        except OSError:
            pass

    def _save_state_now(self):
        self._save_state_job = None
        state = {
            "math_inputs": {
                "pumpkin_mass": self.var_math_mass.get(),
                "efficiency": self.var_math_eff.get(),
                "band_count": self.var_math_bands.get(),
                "target_range": self.var_math_range.get(),
            },
            "regression_inputs": {
                "pred_range": self.var_pred_range.get(),
                "pred_mass": self.var_pred_mass.get(),
            },
            "constants": {
                "SLING_MASS": self.var_const_sling_mass.get(),
                "BAND_STRENGTH": self.var_const_band_strength.get(),
                "BAND_REST_LENGTH": self.var_const_band_rest.get(),
                "LAUNCH_ANGLE_DEG": self.var_const_angle_deg.get(),
                "GRAVITY": self.var_const_gravity.get(),
                "DRAG_COEFFICIENT": self.var_const_drag.get(),
                "AIR_DENSITY": self.var_const_air_rho.get(),
                "PUMPKIN_DENSITY": self.var_const_pumpkin_rho.get(),
                "NEWTON_TO_LBF": self.var_const_n_to_lbf.get(),
            },
            "data_points": self.data_points,
        }
        try:
            with open(DEFAULT_JSON_PATH, mode="w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except OSError:
            pass
        self._save_trials_csv(DEFAULT_CSV_PATH)

    def _load_persisted_data(self):
        """Load saved trials from pumpkin_launch_data.csv and settings from launcher_state.json."""
        self._suppress_trace = True
        loaded_trials = None

        # 1. Load JSON state (inputs, constants, and backup data_points)
        if os.path.exists(DEFAULT_JSON_PATH):
            try:
                with open(DEFAULT_JSON_PATH, mode="r", encoding="utf-8") as f:
                    state = json.load(f)
                m_in = state.get("math_inputs", {})
                if "pumpkin_mass" in m_in:
                    self.var_math_mass.set(str(m_in["pumpkin_mass"]))
                if "efficiency" in m_in:
                    self.var_math_eff.set(str(m_in["efficiency"]))
                if "band_count" in m_in:
                    self.var_math_bands.set(str(m_in["band_count"]))
                if "target_range" in m_in:
                    self.var_math_range.set(str(m_in["target_range"]))

                r_in = state.get("regression_inputs", {})
                if "pred_range" in r_in:
                    self.var_pred_range.set(str(r_in["pred_range"]))
                if "pred_mass" in r_in:
                    self.var_pred_mass.set(str(r_in["pred_mass"]))

                c_in = state.get("constants", {})
                const_map = [
                    ("SLING_MASS", self.var_const_sling_mass),
                    ("BAND_STRENGTH", self.var_const_band_strength),
                    ("BAND_REST_LENGTH", self.var_const_band_rest),
                    ("LAUNCH_ANGLE_DEG", self.var_const_angle_deg),
                    ("GRAVITY", self.var_const_gravity),
                    ("DRAG_COEFFICIENT", self.var_const_drag),
                    ("AIR_DENSITY", self.var_const_air_rho),
                    ("PUMPKIN_DENSITY", self.var_const_pumpkin_rho),
                    ("NEWTON_TO_LBF", self.var_const_n_to_lbf),
                ]
                for key, var in const_map:
                    if key in c_in:
                        var.set(str(c_in[key]))

                if isinstance(state.get("data_points"), list):
                    loaded_trials = [
                        {
                            "force": float(pt["force"]),
                            "mass": float(pt["mass"]),
                            "range": float(pt["range"]),
                        }
                        for pt in state["data_points"]
                        if "force" in pt and "mass" in pt and "range" in pt
                    ]
            except Exception:
                pass

        # 2. If pumpkin_launch_data.csv exists, prefer its trial rows so external CSV edits work seamlessly
        if os.path.exists(DEFAULT_CSV_PATH):
            try:
                csv_trials = []
                with open(DEFAULT_CSV_PATH, mode="r", newline="", encoding="utf-8-sig") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if not row or len(row) < 3:
                            continue
                        try:
                            csv_trials.append(
                                {
                                    "force": float(row[0].strip()),
                                    "mass": float(row[1].strip()),
                                    "range": float(row[2].strip()),
                                }
                            )
                        except ValueError:
                            continue
                if csv_trials:
                    loaded_trials = csv_trials
            except Exception:
                pass

        self._suppress_trace = False
        self._on_constants_changed()

        if loaded_trials is not None:
            self.data_points = loaded_trials
            self._fit_plane_and_refresh()
        else:
            self._load_sample_data(silent=True)

    def _apply_styles(self):
        self.root.option_add("*TCombobox*Listbox.background", SURFACE_1)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT_WHITE)
        self.root.option_add("*TCombobox*Listbox.selectBackground", MCC_GOLD)
        self.root.option_add("*TCombobox*Listbox.selectForeground", BG_MAIN)
        self.root.option_add("*Font", FONT_BODY)

        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.style.configure("TFrame", background=BG_MAIN, borderwidth=0)
        self.style.configure("Surface.TFrame", background=SURFACE_1, borderwidth=0)

        self.style.configure("TLabel", background=BG_MAIN, foreground=TEXT_BODY, font=FONT_BODY)
        self.style.configure("Header.TLabel", background=BG_MAIN, foreground=MCC_GOLD, font=FONT_HEADER)
        self.style.configure("Subheader.TLabel", background=BG_MAIN, foreground=TEXT_MUTED, font=FONT_BOLD)
        self.style.configure("Micro.TLabel", background=BG_MAIN, foreground=MCC_GOLD, font=FONT_MICRO)
        self.style.configure("Muted.TLabel", background=BG_MAIN, foreground=TEXT_MUTED, font=FONT_MUTED)
        self.style.configure("Value.TLabel", background=BG_MAIN, foreground=TEXT_WHITE, font=FONT_BOLD)
        self.style.configure("ReadoutHuge.TLabel", background=SURFACE_1, foreground=MCC_GOLD, font=FONT_HUGE)
        self.style.configure("Equation.TLabel", background=BG_MAIN, foreground=TEXT_WHITE, font=FONT_EQ)
        self.style.configure("StatusOk.TLabel", background=SURFACE_1, foreground=SUCCESS_GREEN, font=FONT_BOLD)
        self.style.configure("StatusErr.TLabel", background=SURFACE_1, foreground=ERROR_RED, font=FONT_BOLD)
        self.style.configure("StatusOkBg.TLabel", background=BG_MAIN, foreground=SUCCESS_GREEN, font=FONT_BOLD)
        self.style.configure("StatusErrBg.TLabel", background=BG_MAIN, foreground=ERROR_RED, font=FONT_BOLD)

        self.style.configure(
            "TNotebook",
            background=BG_MAIN,
            bordercolor=MCC_GOLD,
            borderwidth=1,
            tabmargins=(0, 0, 0, 0),
        )
        self.style.configure(
            "TNotebook.Tab",
            background=SURFACE_1,
            foreground=MCC_GOLD,
            bordercolor=MCC_GOLD,
            lightcolor=SURFACE_1,
            darkcolor=SURFACE_1,
            font=FONT_BOLD,
            padding=(18, 10),
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", MCC_GOLD), ("active", SURFACE_2)],
            foreground=[("selected", BG_MAIN), ("active", HOVER_GOLD)],
        )

        self.style.configure(
            "TButton",
            background=SURFACE_1,
            foreground=MCC_GOLD,
            bordercolor=MCC_GOLD,
            lightcolor=MCC_GOLD,
            darkcolor=MCC_GOLD,
            borderwidth=1,
            focusthickness=1,
            focuscolor=MCC_GOLD,
            relief="solid",
            font=FONT_MICRO,
            padding=(12, 7),
        )
        self.style.map(
            "TButton",
            background=[("active", MCC_GOLD), ("pressed", MCC_GOLD), ("disabled", SURFACE_1)],
            foreground=[("active", BG_MAIN), ("pressed", BG_MAIN), ("disabled", TEXT_DISABLED)],
            bordercolor=[("disabled", BORDER_MID)],
        )

        self.style.configure(
            "Primary.TButton",
            background=MCC_GOLD,
            foreground=BG_MAIN,
            bordercolor=MCC_GOLD,
            lightcolor=MCC_GOLD,
            darkcolor=MCC_GOLD,
            borderwidth=1,
            focusthickness=1,
            focuscolor=TEXT_WHITE,
            relief="solid",
            font=FONT_MICRO,
            padding=(14, 7),
        )
        self.style.map(
            "Primary.TButton",
            background=[("active", HOVER_GOLD), ("pressed", HOVER_GOLD), ("disabled", BORDER_MID)],
            foreground=[("active", BG_MAIN), ("pressed", BG_MAIN), ("disabled", TEXT_DISABLED)],
        )

        self.style.configure(
            "Destructive.TButton",
            background=SURFACE_1,
            foreground=ERROR_RED,
            bordercolor=ERROR_RED,
            lightcolor=ERROR_RED,
            darkcolor=ERROR_RED,
            borderwidth=1,
            focusthickness=1,
            focuscolor=ERROR_RED,
            relief="solid",
            font=FONT_MICRO,
            padding=(12, 6),
        )
        self.style.map(
            "Destructive.TButton",
            background=[("active", ERROR_RED), ("pressed", ERROR_RED)],
            foreground=[("active", BG_MAIN), ("pressed", BG_MAIN)],
        )

        self.style.configure(
            "TRadiobutton",
            background=BG_MAIN,
            foreground=TEXT_WHITE,
            indicatorbackground=SURFACE_1,
            indicatorforeground=MCC_GOLD,
            upperbordercolor=MCC_GOLD,
            lowerbordercolor=MCC_GOLD,
            focuscolor=MCC_GOLD,
            font=FONT_BOLD,
        )
        self.style.map(
            "TRadiobutton",
            background=[("active", BG_MAIN)],
            foreground=[("selected", MCC_GOLD), ("active", HOVER_GOLD)],
        )

        self.style.configure(
            "Treeview",
            background=SURFACE_1,
            fieldbackground=SURFACE_1,
            foreground=TEXT_WHITE,
            bordercolor=MCC_GOLD,
            lightcolor=BORDER_DARK,
            darkcolor=BORDER_DARK,
            borderwidth=1,
            rowheight=32,
            font=FONT_MICRO,
        )
        self.style.configure(
            "Treeview.Heading",
            background=SURFACE_2,
            foreground=MCC_GOLD,
            bordercolor=BORDER_MID,
            lightcolor=BORDER_MID,
            darkcolor=BORDER_MID,
            borderwidth=1,
            relief="flat",
            font=FONT_MICRO,
            padding=(8, 6),
        )
        self.style.map(
            "Treeview.Heading",
            background=[("active", SURFACE_3)],
            foreground=[("active", HOVER_GOLD)],
        )
        self.style.map(
            "Treeview",
            background=[("selected", MCC_GOLD)],
            foreground=[("selected", BG_MAIN)],
        )

        self.style.configure(
            "Vertical.TScrollbar",
            background=MCC_GOLD,
            troughcolor=SURFACE_1,
            bordercolor=BORDER_DARK,
            arrowcolor=BG_MAIN,
            relief="flat",
        )
        self.style.map(
            "Vertical.TScrollbar",
            background=[("active", HOVER_GOLD), ("!active", BORDER_MID)],
        )

    def _create_gold_panel(self, parent, title_text: str, pad: int = 12, surface_bg: str = BG_MAIN):
        """Lightweight single-widget LabelFrame for fast layout on Raspberry Pi."""
        frame = tk.LabelFrame(
            parent,
            text=f" {title_text.upper()} ",
            bg=surface_bg,
            fg=MCC_GOLD,
            font=FONT_MICRO,
            bd=1,
            relief="solid",
            highlightbackground=MCC_GOLD,
            highlightcolor=MCC_GOLD,
            highlightthickness=1,
            padx=pad,
            pady=pad,
        )
        return frame, frame

    def _create_entry(self, parent, textvariable: tk.StringVar, width: int = 14) -> tk.Entry:
        """Create a square-cornered dark entry with 1px gold border and larger readable font."""
        return tk.Entry(
            parent,
            textvariable=textvariable,
            width=width,
            bg=SURFACE_1,
            fg=TEXT_WHITE,
            insertbackground=MCC_GOLD,
            selectbackground=MCC_GOLD,
            selectforeground=BG_MAIN,
            relief="flat",
            bd=5,
            highlightthickness=1,
            highlightbackground=MCC_GOLD,
            highlightcolor=HOVER_GOLD,
            font=FONT_ENTRY,
        )

    def _build_top_bar(self):
        top_container = tk.Frame(self.root, bg=BG_MAIN, bd=0)
        top_container.pack(fill=tk.X)

        bar_inner = tk.Frame(top_container, bg=BG_MAIN, padx=18, pady=10)
        bar_inner.pack(fill=tk.X)

        ttk.Label(
            bar_inner,
            text="ELC PUMPKIN LAUNCHER 2026",
            style="Header.TLabel",
        ).pack(side=tk.LEFT)

        self.lbl_global_status = ttk.Label(
            bar_inner,
            text="[OFFLINE AUTO-CALC READY]",
            style="Subheader.TLabel",
        )
        self.lbl_global_status.pack(side=tk.RIGHT)

        tk.Frame(top_container, bg=MCC_GOLD, height=1, bd=0).pack(fill=tk.X)

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)

        self.tab_math = ttk.Frame(self.notebook, padding=10)
        self.tab_regression = ttk.Frame(self.notebook, padding=10)
        self.tab_settings = ttk.Frame(self.notebook, padding=14)

        self.notebook.add(self.tab_math, text="[1] PHYSICS MODEL")
        self.notebook.add(self.tab_regression, text="[2] 3D PLANE REGRESSION")
        self.notebook.add(self.tab_settings, text="[3] LAUNCHER SETTINGS (CONSTANTS)")

        self._build_math_tab()
        self._build_regression_tab()
        self._build_settings_tab()

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, _event):
        if self.notebook.index("current") == 1:
            self._schedule_plot_redraw()

    # =========================================================================
    # TAB 1: PHYSICS MATH MODEL (AUTO-CALCULATING)
    # =========================================================================
    def _build_math_tab(self):
        left_col = ttk.Frame(self.tab_math)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 14))

        right_col = ttk.Frame(self.tab_math)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- Non-Constant Inputs Panel ---
        in_outer, in_frame = self._create_gold_panel(left_col, "NON-CONSTANT INPUTS (AUTO-UPDATE)")
        in_outer.pack(fill=tk.X, pady=(0, 12))

        self.var_math_mass = tk.StringVar(value=str(es.pumpkin_mass))
        self.var_math_eff = tk.StringVar(value=str(es.efficiency))
        self.var_math_bands = tk.StringVar(value=str(es.band_count))
        self.var_math_range = tk.StringVar(value=str(es.target_range))

        fields = [
            ("PUMPKIN MASS m_p (KG)", self.var_math_mass),
            ("EFFICIENCY n (0-1)", self.var_math_eff),
            ("BAND COUNT B", self.var_math_bands),
            ("TARGET RANGE R (FT)", self.var_math_range),
        ]
        for idx, (label_text, var) in enumerate(fields):
            ttk.Label(in_frame, text=label_text, style="Micro.TLabel").grid(
                row=idx, column=0, sticky=tk.W, pady=7
            )
            ent = self._create_entry(in_frame, textvariable=var, width=14)
            ent.grid(row=idx, column=1, sticky=tk.EW, padx=(14, 0), pady=7)
            var.trace_add("write", lambda *_args: self._schedule_math_calc())

        # Preset range buttons
        preset_frame = ttk.Frame(in_frame)
        preset_frame.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=(6, 6))
        ttk.Label(preset_frame, text="QUICK RANGE:", style="Micro.TLabel").pack(
            side=tk.LEFT, padx=(0, 8)
        )
        for r_ft in (50, 100, 200, 300):
            ttk.Button(
                preset_frame,
                text=f"{r_ft}FT",
                width=6,
                command=lambda r=r_ft: self._set_math_range(r),
            ).pack(side=tk.LEFT, padx=3)

        btn_row = ttk.Frame(in_frame)
        btn_row.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0))
        ttk.Button(
            btn_row,
            text="RESET INPUT DEFAULTS",
            command=self._reset_math_defaults,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(
            btn_row,
            text="EDIT CONSTANTS >",
            command=lambda: self.notebook.select(self.tab_settings),
        ).pack(side=tk.LEFT)

        # --- Active Constants Summary Panel ---
        const_outer, const_frame = self._create_gold_panel(left_col, "ACTIVE LAUNCHER CONSTANTS")
        const_outer.pack(fill=tk.BOTH, expand=True)

        self.const_summary_vars = {}
        const_rows = [
            ("SLING_MASS", "SLING MASS (m_s)"),
            ("BAND_STRENGTH", "BAND STRENGTH (S)"),
            ("BAND_REST_LENGTH", "BAND REST LEN (L_0)"),
            ("LAUNCH_ANGLE_DEG", "LAUNCH ANGLE (j)"),
            ("GRAVITY", "GRAVITY (g)"),
            ("DRAG_COEFFICIENT", "DRAG COEFF (c)"),
            ("AIR_DENSITY", "AIR DENSITY (p)"),
            ("PUMPKIN_DENSITY", "PUMPKIN DENSITY"),
            ("NEWTON_TO_LBF", "N TO LBF FACTOR"),
        ]
        for idx, (key, label_text) in enumerate(const_rows):
            ttk.Label(const_frame, text=label_text, style="Muted.TLabel").grid(
                row=idx, column=0, sticky=tk.W, pady=3
            )
            sv = tk.StringVar()
            self.const_summary_vars[key] = sv
            ttk.Label(const_frame, textvariable=sv, style="Value.TLabel").grid(
                row=idx, column=1, sticky=tk.W, padx=(16, 0), pady=3
            )

        # --- Right Column: Giant Output Readout ---
        res_outer, res_frame = self._create_gold_panel(
            right_col,
            "CALCULATED PULLBACK FORCE [F = 0.2248 * (m_total * v_0^2) / (n * d)]",
            pad=14,
            surface_bg=SURFACE_1,
        )
        res_outer.pack(fill=tk.X, pady=(0, 12))

        self.lbl_math_force_lbf = ttk.Label(res_frame, text="-- LBF", style="ReadoutHuge.TLabel")
        self.lbl_math_force_lbf.pack(anchor=tk.W)

        self.lbl_math_force_n = ttk.Label(res_frame, text="[WAITING]", style="StatusOk.TLabel")
        self.lbl_math_force_n.pack(anchor=tk.W, pady=(4, 0))

        # --- Preset Ranges Table (Pre-allocated rows for zero-lag updates) ---
        tbl_outer, tbl_frame = self._create_gold_panel(
            right_col, "TARGET RANGE MATRIX (50 / 100 / 200 / 300 FT)"
        )
        tbl_outer.pack(fill=tk.X, pady=(0, 12))

        cols = ("range_ft", "v_vac", "v_drag", "draw_d", "stretch_sr", "force_lbf", "force_n")
        self.tree_math_presets = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=4)
        self.tree_math_presets.heading("range_ft", text="RANGE (FT)")
        self.tree_math_presets.heading("v_vac", text="v_vac (M/S)")
        self.tree_math_presets.heading("v_drag", text="v_0 (M/S)")
        self.tree_math_presets.heading("draw_d", text="d (M)")
        self.tree_math_presets.heading("stretch_sr", text="S_r (d/L_0)")
        self.tree_math_presets.heading("force_lbf", text="FORCE (LBF)")
        self.tree_math_presets.heading("force_n", text="FORCE (N)")

        for c in cols:
            self.tree_math_presets.column(c, anchor=tk.CENTER, width=95)
        self.tree_math_presets.pack(fill=tk.X)

        self._math_preset_iids = [
            self.tree_math_presets.insert("", tk.END, values=(f"{r} ft", "--", "--", "--", "--", "--", "--"))
            for r in (50, 100, 200, 300)
        ]

        # --- Intermediate Physics Quantities ---
        det_outer, det_frame = self._create_gold_panel(right_col, "INTERMEDIATE MODEL VALUES")
        det_outer.pack(fill=tk.BOTH, expand=True)

        self.math_detail_vars = {}
        detail_labels = [
            ("target_range_m", "TARGET RANGE 0.3048*R (M)"),
            ("launched_mass", "TOTAL MASS m_total = m_p + m_s (KG)"),
            ("area", "CROSS-SECTIONAL AREA A (M^2)"),
            ("drag_scale", "DRAG VELOCITY SCALE D (M/S)"),
            ("v_vacuum", "VACUUM VELOCITY v_vac (M/S)"),
            ("v_initial", "INITIAL VELOCITY v_0 (M/S)"),
            ("stiffness", "BAND STIFFNESS S*B/L_0 (N/M)"),
            ("elongation", "ELONGATION FACTOR E_L (S)"),
            ("draw_dist", "DRAW DISTANCE d = E_L * v_0 (M)"),
            ("stretch_ratio", "STRETCH RATIO S_r = d / L_0"),
        ]
        for idx, (key, title) in enumerate(detail_labels):
            ttk.Label(det_frame, text=title, style="Muted.TLabel").grid(
                row=idx, column=0, sticky=tk.W, pady=3
            )
            var = tk.StringVar(value="--")
            self.math_detail_vars[key] = var
            ttk.Label(det_frame, textvariable=var, style="Value.TLabel").grid(
                row=idx, column=1, sticky=tk.W, padx=(20, 0), pady=3
            )

    def _schedule_math_calc(self):
        if self._suppress_trace:
            return
        if self._math_calc_job is not None:
            self.root.after_cancel(self._math_calc_job)
        self._math_calc_job = self.root.after(25, self.calculate_math_model)

    def _set_math_range(self, r_ft: float):
        self.var_math_range.set(str(r_ft))

    def _reset_math_defaults(self):
        self._suppress_trace = True
        self.var_math_mass.set("0.9")
        self.var_math_eff.set("0.8")
        self.var_math_bands.set("24")
        self.var_math_range.set("300")
        self._suppress_trace = False
        self.calculate_math_model()

    @staticmethod
    def _eval_math_fast(mass: float, eff: float, bands: float, target_ft: float):
        """Fast inline evaluation of the physics model equations without module-call overhead."""
        target_m = target_ft * 0.3048
        l_mass = mass + es.SLING_MASS
        area = ((((3.0 * (mass / es.PUMPKIN_DENSITY)) / (4.0 * math.pi)) ** (1.0 / 3.0)) ** 2.0) * math.pi
        d_scale = ((2.0 * mass * es.GRAVITY) / (es.AIR_DENSITY * area * es.DRAG_COEFFICIENT)) ** 0.5

        sin_2j = math.sin(2.0 * es.LAUNCH_ANGLE)
        sin_j = math.sin(es.LAUNCH_ANGLE)
        rg_sin2j = (target_m * es.GRAVITY) / sin_2j
        v_vac = rg_sin2j ** 0.5
        v_init = (rg_sin2j * (1.0 + ((4.0 * v_vac * sin_j) / (3.0 * d_scale)))) ** 0.5

        stiffness = es.BAND_STRENGTH * bands / es.BAND_REST_LENGTH
        elong = (l_mass / (eff * stiffness)) ** 0.5
        d_dist = elong * v_init
        s_ratio = d_dist / es.BAND_REST_LENGTH
        f_n = (l_mass * (v_init ** 2.0)) / (eff * d_dist)
        f_lbf = es.newton_to_pound_force * f_n

        return {
            "target_m": target_m,
            "area": area,
            "drag_scale": d_scale,
            "v_vac": v_vac,
            "v_init": v_init,
            "launched_mass": l_mass,
            "stiffness": stiffness,
            "elongation": elong,
            "draw_dist": d_dist,
            "stretch_ratio": s_ratio,
            "force_lbf": f_lbf,
            "force_n": f_n,
        }

    def _refresh_constant_summary_labels(self):
        deg = math.degrees(es.LAUNCH_ANGLE)
        self.const_summary_vars["SLING_MASS"].set(f"{es.SLING_MASS:g} kg")
        self.const_summary_vars["BAND_STRENGTH"].set(f"{es.BAND_STRENGTH:.4f} N")
        self.const_summary_vars["BAND_REST_LENGTH"].set(f"{es.BAND_REST_LENGTH:g} m")
        self.const_summary_vars["LAUNCH_ANGLE_DEG"].set(f"{deg:g} deg ({es.LAUNCH_ANGLE:.4f} rad)")
        self.const_summary_vars["GRAVITY"].set(f"{es.GRAVITY:g} m/s^2")
        self.const_summary_vars["DRAG_COEFFICIENT"].set(f"{es.DRAG_COEFFICIENT:g}")
        self.const_summary_vars["AIR_DENSITY"].set(f"{es.AIR_DENSITY:g} kg/m^3")
        self.const_summary_vars["PUMPKIN_DENSITY"].set(f"{es.PUMPKIN_DENSITY:g} kg/m^3")
        self.const_summary_vars["NEWTON_TO_LBF"].set(f"{es.newton_to_pound_force:g} lbf/N")

    def calculate_math_model(self):
        self._math_calc_job = None
        self._refresh_constant_summary_labels()
        try:
            mass = float(self.var_math_mass.get())
            eff = float(self.var_math_eff.get())
            bands = float(self.var_math_bands.get())
            target_ft = float(self.var_math_range.get())

            if mass <= 0:
                raise ValueError("Pumpkin mass must be > 0 kg.")
            if eff <= 0 or eff > 1.0:
                raise ValueError("Efficiency must be in (0, 1].")
            if bands <= 0:
                raise ValueError("Band count must be > 0.")
            if target_ft <= 0:
                raise ValueError("Target range must be > 0 ft.")

            sin_2j = math.sin(2.0 * es.LAUNCH_ANGLE)
            if sin_2j <= 1e-9:
                raise ValueError("Launch angle must be between 0 and 90 deg.")

            # Keep equation_solver module state synchronized
            es.pumpkin_mass = mass
            es.efficiency = eff
            es.band_count = bands
            es.target_range = target_ft
            es.target_range_converted = target_ft * 0.3048

            res = self._eval_math_fast(mass, eff, bands, target_ft)

            self.lbl_math_force_lbf.config(text=f"{res['force_lbf']:.2f} LBF")
            self.lbl_math_force_n.config(
                text=(
                    f"[OK] {res['force_n']:.2f} N  |  "
                    f"DRAW d = {res['draw_dist']:.3f} M  |  "
                    f"STRETCH S_r = {res['stretch_ratio']:.2f}"
                ),
                style="StatusOk.TLabel",
            )
            self.lbl_global_status.config(text="[MODEL UPDATED]")

            self.math_detail_vars["target_range_m"].set(f"{res['target_m']:.4f} m")
            self.math_detail_vars["launched_mass"].set(f"{res['launched_mass']:.4f} kg")
            self.math_detail_vars["area"].set(f"{res['area']:.6f} m^2")
            self.math_detail_vars["drag_scale"].set(f"{res['drag_scale']:.4f} m/s")
            self.math_detail_vars["v_vacuum"].set(f"{res['v_vac']:.4f} m/s")
            self.math_detail_vars["v_initial"].set(f"{res['v_init']:.4f} m/s")
            self.math_detail_vars["stiffness"].set(f"{res['stiffness']:.2f} N/m")
            self.math_detail_vars["elongation"].set(f"{res['elongation']:.6f} s")
            self.math_detail_vars["draw_dist"].set(f"{res['draw_dist']:.4f} m")
            self.math_detail_vars["stretch_ratio"].set(f"{res['stretch_ratio']:.4f}")

            for iid, r_ft in zip(self._math_preset_iids, (50, 100, 200, 300)):
                r_res = self._eval_math_fast(mass, eff, bands, float(r_ft))
                self.tree_math_presets.item(
                    iid,
                    values=(
                        f"{r_ft} ft",
                        f"{r_res['v_vac']:.2f}",
                        f"{r_res['v_init']:.2f}",
                        f"{r_res['draw_dist']:.3f}",
                        f"{r_res['stretch_ratio']:.2f}",
                        f"{r_res['force_lbf']:.2f} lbf",
                        f"{r_res['force_n']:.1f} N",
                    ),
                )
            self._schedule_save_state()

        except ValueError as exc:
            self.lbl_math_force_lbf.config(text="-- LBF")
            self.lbl_math_force_n.config(text=f"[INPUT PENDING] {exc}", style="StatusErr.TLabel")
            self.lbl_global_status.config(text="[CHECK INPUT]")

    # =========================================================================
    # TAB 2: EMPIRICAL LINEAR REGRESSION (3D PLANE FIT, AUTO-CALCULATING)
    # =========================================================================
    def _build_regression_tab(self):
        left_pane = ttk.Frame(self.tab_regression)
        left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 14))

        right_pane = ttk.Frame(self.tab_regression)
        right_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- Step 1: Data Entry ---
        add_outer, add_frame = self._create_gold_panel(left_pane, "ADD TRIAL DATA (FORCE / MASS / RANGE)")
        add_outer.pack(fill=tk.X, pady=(0, 10))

        self.var_data_force = tk.StringVar()
        self.var_data_mass = tk.StringVar()
        self.var_data_range = tk.StringVar()

        fields_row = ttk.Frame(add_frame)
        fields_row.pack(fill=tk.X)

        ttk.Label(fields_row, text="FORCE (LBF)", style="Micro.TLabel").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 4)
        )
        ent_df = self._create_entry(fields_row, textvariable=self.var_data_force, width=6)
        ent_df.grid(row=0, column=1, padx=(0, 8))

        ttk.Label(fields_row, text="MASS (KG)", style="Micro.TLabel").grid(
            row=0, column=2, sticky=tk.W, padx=(0, 4)
        )
        ent_dm = self._create_entry(fields_row, textvariable=self.var_data_mass, width=6)
        ent_dm.grid(row=0, column=3, padx=(0, 8))

        ttk.Label(fields_row, text="RANGE (FT)", style="Micro.TLabel").grid(
            row=0, column=4, sticky=tk.W, padx=(0, 4)
        )
        ent_dr = self._create_entry(fields_row, textvariable=self.var_data_range, width=6)
        ent_dr.grid(row=0, column=5, padx=(0, 8))

        ttk.Button(
            fields_row,
            text="ADD POINT",
            style="Primary.TButton",
            command=self.add_data_point,
        ).grid(row=0, column=6, sticky=tk.E)

        for ent in (ent_df, ent_dm, ent_dr):
            ent.bind("<Return>", lambda _e: self.add_data_point())

        # --- Recorded Trials Table ---
        tbl_outer, tbl_frame = self._create_gold_panel(left_pane, "RECORDED LAUNCH TRIALS (MIN 3 POINTS)")
        tbl_outer.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        cols = ("idx", "force", "mass", "range", "pred_force", "residual")
        self.tree_data = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=10)
        self.tree_data.heading("idx", text="ID")
        self.tree_data.heading("force", text="FORCE (LBF)")
        self.tree_data.heading("mass", text="MASS (KG)")
        self.tree_data.heading("range", text="RANGE (FT)")
        self.tree_data.heading("pred_force", text="FIT (LBF)")
        self.tree_data.heading("residual", text="ERR (LBF)")

        self.tree_data.column("idx", width=38, anchor=tk.CENTER)
        self.tree_data.column("force", width=92, anchor=tk.CENTER)
        self.tree_data.column("mass", width=86, anchor=tk.CENTER)
        self.tree_data.column("range", width=88, anchor=tk.CENTER)
        self.tree_data.column("pred_force", width=92, anchor=tk.CENTER)
        self.tree_data.column("residual", width=86, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(tbl_frame, orient=tk.VERTICAL, command=self.tree_data.yview)
        self.tree_data.configure(yscrollcommand=scrollbar.set)
        self.tree_data.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Table action buttons
        tbl_btns = ttk.Frame(left_pane)
        tbl_btns.pack(fill=tk.X)

        ttk.Button(
            tbl_btns,
            text="DELETE SELECTED",
            style="Destructive.TButton",
            command=self.delete_selected_points,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            tbl_btns,
            text="CLEAR ALL",
            style="Destructive.TButton",
            command=self.clear_all_points,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            tbl_btns,
            text="LOAD SAMPLE",
            command=lambda: self._load_sample_data(silent=False),
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(tbl_btns, text="IMPORT CSV", command=self.import_csv).pack(side=tk.RIGHT)
        ttk.Button(tbl_btns, text="EXPORT CSV", command=self.export_csv).pack(
            side=tk.RIGHT, padx=(0, 6)
        )

        # --- Right Pane Step 2: Fitted Plane Equation ---
        fit_outer, fit_frame = self._create_gold_panel(
            right_pane, "FITTED 3D PLANE MODEL [FORCE = A*RANGE + B*MASS + C]", pad=8
        )
        fit_outer.pack(fill=tk.X, pady=(0, 8))

        self.lbl_plane_eq = ttk.Label(
            fit_frame,
            text="[WAITING FOR >= 3 DATA POINTS]",
            style="Equation.TLabel",
        )
        self.lbl_plane_eq.pack(anchor=tk.W)

        self.lbl_plane_stats = ttk.Label(
            fit_frame,
            text="R^2 = --  |  RMSE = --",
            style="Muted.TLabel",
        )
        self.lbl_plane_stats.pack(anchor=tk.W, pady=(4, 0))

        # --- Right Pane Step 3: Auto-Predicted Force Readout ---
        pred_outer, pred_frame = self._create_gold_panel(
            right_pane, "REQUIRED PULLBACK FORCE FROM PLANE (AUTO-UPDATE)", pad=10, surface_bg=SURFACE_1
        )
        pred_outer.pack(fill=tk.X, pady=(0, 8))

        self.var_pred_range = tk.StringVar(value="200")
        self.var_pred_mass = tk.StringVar(value="0.9")

        pred_inputs = tk.Frame(pred_frame, bg=SURFACE_1)
        pred_inputs.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            pred_inputs,
            text="DESIRED RANGE (FT):",
            bg=SURFACE_1,
            fg=MCC_GOLD,
            font=FONT_MICRO,
        ).grid(row=0, column=0, sticky=tk.W, pady=4)

        range_btn_frame = tk.Frame(pred_inputs, bg=SURFACE_1)
        range_btn_frame.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=4)

        for r_ft in (50, 100, 200, 300):
            ttk.Radiobutton(
                range_btn_frame,
                text=f"{r_ft}FT",
                value=str(r_ft),
                variable=self.var_pred_range,
            ).pack(side=tk.LEFT, padx=(0, 10))

        ent_pred_range = self._create_entry(range_btn_frame, textvariable=self.var_pred_range, width=8)
        ent_pred_range.pack(side=tk.LEFT, padx=(6, 0))

        tk.Label(
            pred_inputs,
            text="PUMPKIN MASS (KG):",
            bg=SURFACE_1,
            fg=MCC_GOLD,
            font=FONT_MICRO,
        ).grid(row=1, column=0, sticky=tk.W, pady=4)

        mass_row = tk.Frame(pred_inputs, bg=SURFACE_1)
        mass_row.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=4)
        ent_pred_mass = self._create_entry(mass_row, textvariable=self.var_pred_mass, width=10)
        ent_pred_mass.pack(side=tk.LEFT)

        self.var_pred_range.trace_add("write", lambda *_args: self._schedule_pred_calc())
        self.var_pred_mass.trace_add("write", lambda *_args: self._schedule_pred_calc())

        tk.Frame(pred_frame, bg=BORDER_MID, height=1, bd=0).pack(fill=tk.X, pady=6)

        self.lbl_pred_force = ttk.Label(pred_frame, text="-- LBF", style="ReadoutHuge.TLabel")
        self.lbl_pred_force.pack(anchor=tk.W)

        self.lbl_pred_sub = ttk.Label(
            pred_frame,
            text="Select target range and enter pumpkin mass.",
            style="StatusOk.TLabel",
        )
        self.lbl_pred_sub.pack(anchor=tk.W, pady=(2, 6))

        cols_p = ("r50", "r100", "r200", "r300")
        self.tree_pred_all = ttk.Treeview(pred_frame, columns=cols_p, show="headings", height=1)
        for c, label in zip(cols_p, ("50 FT TARGET", "100 FT TARGET", "200 FT TARGET", "300 FT TARGET")):
            self.tree_pred_all.heading(c, text=label)
            self.tree_pred_all.column(c, anchor=tk.CENTER, width=110)
        self.tree_pred_all.pack(fill=tk.X)
        self._pred_row_iid = self.tree_pred_all.insert("", tk.END, values=("--", "--", "--", "--"))

        # --- Right Pane Step 4: Interactive 3D Surface / Plane Graph ---
        plot_outer, plot_frame = self._create_gold_panel(
            right_pane,
            "3D PLANE GRAPH (DRAG MOUSE TO ROTATE: X=RANGE, Y=MASS, Z=FORCE)",
            pad=6,
        )
        plot_outer.pack(fill=tk.BOTH, expand=True)

        ctrl_bar = ttk.Frame(plot_frame)
        ctrl_bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(
            ctrl_bar,
            text="[DRAG CANVAS TO ORBIT 3D VIEW]",
            style="Muted.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Button(
            ctrl_bar,
            text="RESET 3D VIEW",
            command=self._reset_3d_view,
        ).pack(side=tk.RIGHT)

        self.canvas_plot = tk.Canvas(
            plot_frame,
            bg=SURFACE_1,
            highlightthickness=1,
            highlightbackground=BORDER_MID,
            bd=0,
            cursor="crosshair",
        )
        self.canvas_plot.pack(fill=tk.BOTH, expand=True)
        self.canvas_plot.bind("<Configure>", lambda _e: self._schedule_plot_redraw())
        self.canvas_plot.bind("<ButtonPress-1>", self._on_plot_press)
        self.canvas_plot.bind("<B1-Motion>", self._on_plot_drag)
        self.canvas_plot.bind("<ButtonRelease-1>", self._on_plot_release)

    # =========================================================================
    # TAB 3: LAUNCHER SETTINGS / CONSTANTS PANEL
    # =========================================================================
    def _build_settings_tab(self):
        container = ttk.Frame(self.tab_settings)
        container.pack(fill=tk.BOTH, expand=True)

        settings_outer, settings_frame = self._create_gold_panel(
            container,
            "LAUNCHER PHYSICAL CONSTANTS (CHANGES APPLY AUTOMATICALLY)",
            pad=16,
        )
        settings_outer.pack(fill=tk.BOTH, expand=True)

        self.var_const_sling_mass = tk.StringVar(value=str(DEFAULT_CONSTANTS["SLING_MASS"]))
        self.var_const_band_strength = tk.StringVar(value=f"{DEFAULT_CONSTANTS['BAND_STRENGTH']:.4f}")
        self.var_const_band_rest = tk.StringVar(value=str(DEFAULT_CONSTANTS["BAND_REST_LENGTH"]))
        self.var_const_angle_deg = tk.StringVar(value=str(DEFAULT_CONSTANTS["LAUNCH_ANGLE_DEG"]))
        self.var_const_gravity = tk.StringVar(value=str(DEFAULT_CONSTANTS["GRAVITY"]))
        self.var_const_drag = tk.StringVar(value=str(DEFAULT_CONSTANTS["DRAG_COEFFICIENT"]))
        self.var_const_air_rho = tk.StringVar(value=str(DEFAULT_CONSTANTS["AIR_DENSITY"]))
        self.var_const_pumpkin_rho = tk.StringVar(value=str(DEFAULT_CONSTANTS["PUMPKIN_DENSITY"]))
        self.var_const_n_to_lbf = tk.StringVar(value=str(DEFAULT_CONSTANTS["NEWTON_TO_LBF"]))

        setting_specs = [
            ("SLING MASS m_s (KG)", self.var_const_sling_mass, "Mass of the pouch/sling assembly accelerated by bands"),
            ("SINGLE BAND STRENGTH S (N)", self.var_const_band_strength, "Default: 4.4482 * ((14.3 + 21.3/2) / 2) = 55.4913 N"),
            ("BAND REST LENGTH L_0 (M)", self.var_const_band_rest, "Unstretched length of rubber bands in meters (0.254 m = 10 in)"),
            ("LAUNCH ANGLE j (DEGREES)", self.var_const_angle_deg, "Elevation angle of the launcher track (0 to 90 degrees)"),
            ("GRAVITY g (M/S^2)", self.var_const_gravity, "Gravitational acceleration (standard: 9.81 m/s^2)"),
            ("DRAG COEFFICIENT c", self.var_const_drag, "Aerodynamic sphere/pumpkin drag coefficient (default: 0.55)"),
            ("AIR DENSITY p (KG/M^3)", self.var_const_air_rho, "Local air density (Rochester default: 1.21 kg/m^3)"),
            ("PUMPKIN DENSITY (KG/M^3)", self.var_const_pumpkin_rho, "Average pumpkin density used for sphere radius (default: 800 kg/m^3)"),
            ("NEWTON TO LBF CONVERSION", self.var_const_n_to_lbf, "Conversion factor from Newtons to pounds-force (0.2248 lbf/N)"),
        ]

        for idx, (label_text, var, desc) in enumerate(setting_specs):
            ttk.Label(settings_frame, text=label_text, style="Micro.TLabel").grid(
                row=idx, column=0, sticky=tk.W, pady=7
            )
            ent = self._create_entry(settings_frame, textvariable=var, width=16)
            ent.grid(row=idx, column=1, sticky=tk.W, padx=(18, 18), pady=7)
            ttk.Label(settings_frame, text=desc, style="Muted.TLabel").grid(
                row=idx, column=2, sticky=tk.W, pady=7
            )
            var.trace_add("write", lambda *_args: self._schedule_const_calc())

        action_bar = ttk.Frame(settings_frame)
        action_bar.grid(row=len(setting_specs), column=0, columnspan=3, sticky=tk.EW, pady=(18, 0))

        self.lbl_settings_status = ttk.Label(
            action_bar,
            text="[OK] ALL CONSTANTS VALID AND ACTIVE",
            style="StatusOkBg.TLabel",
        )
        self.lbl_settings_status.pack(side=tk.LEFT)

        ttk.Button(
            action_bar,
            text="RESET CONSTANTS TO DEFAULTS",
            style="Primary.TButton",
            command=self._reset_constants_defaults,
        ).pack(side=tk.RIGHT)

    def _schedule_const_calc(self):
        if self._suppress_trace:
            return
        if self._const_calc_job is not None:
            self.root.after_cancel(self._const_calc_job)
        self._const_calc_job = self.root.after(25, self._on_constants_changed)

    def _on_constants_changed(self):
        self._const_calc_job = None
        if self._suppress_trace:
            return
        try:
            sling_m = float(self.var_const_sling_mass.get())
            band_s = float(self.var_const_band_strength.get())
            band_l0 = float(self.var_const_band_rest.get())
            angle_deg = float(self.var_const_angle_deg.get())
            grav = float(self.var_const_gravity.get())
            drag_c = float(self.var_const_drag.get())
            air_p = float(self.var_const_air_rho.get())
            pump_p = float(self.var_const_pumpkin_rho.get())
            n_lbf = float(self.var_const_n_to_lbf.get())

            if sling_m < 0:
                raise ValueError("Sling mass must be >= 0.")
            if band_s <= 0 or band_l0 <= 0:
                raise ValueError("Band strength and rest length must be > 0.")
            if not (0.0 < angle_deg < 90.0):
                raise ValueError("Launch angle must be between 0 and 90 degrees.")
            if grav <= 0 or drag_c <= 0 or air_p <= 0 or pump_p <= 0 or n_lbf <= 0:
                raise ValueError("Gravity, drag, densities, and conversion factor must be > 0.")

            es.SLING_MASS = sling_m
            es.BAND_STRENGTH = band_s
            es.BAND_REST_LENGTH = band_l0
            es.LAUNCH_ANGLE = math.radians(angle_deg)
            es.GRAVITY = grav
            es.DRAG_COEFFICIENT = drag_c
            es.AIR_DENSITY = air_p
            es.PUMPKIN_DENSITY = pump_p
            es.newton_to_pound_force = n_lbf

            self.lbl_settings_status.config(
                text="[OK] CONSTANTS UPDATED AND APPLIED TO MODEL",
                style="StatusOkBg.TLabel",
            )
            self.calculate_math_model()
            self.predict_from_plane(silent=True)

        except ValueError as exc:
            self.lbl_settings_status.config(
                text=f"[INVALID CONSTANT] {exc}",
                style="StatusErrBg.TLabel",
            )

    def _reset_constants_defaults(self):
        self._suppress_trace = True
        self.var_const_sling_mass.set(str(DEFAULT_CONSTANTS["SLING_MASS"]))
        self.var_const_band_strength.set(f"{DEFAULT_CONSTANTS['BAND_STRENGTH']:.4f}")
        self.var_const_band_rest.set(str(DEFAULT_CONSTANTS["BAND_REST_LENGTH"]))
        self.var_const_angle_deg.set(str(DEFAULT_CONSTANTS["LAUNCH_ANGLE_DEG"]))
        self.var_const_gravity.set(str(DEFAULT_CONSTANTS["GRAVITY"]))
        self.var_const_drag.set(str(DEFAULT_CONSTANTS["DRAG_COEFFICIENT"]))
        self.var_const_air_rho.set(str(DEFAULT_CONSTANTS["AIR_DENSITY"]))
        self.var_const_pumpkin_rho.set(str(DEFAULT_CONSTANTS["PUMPKIN_DENSITY"]))
        self.var_const_n_to_lbf.set(str(DEFAULT_CONSTANTS["NEWTON_TO_LBF"]))
        self._suppress_trace = False
        self._on_constants_changed()

    def _schedule_plot_redraw(self):
        """Throttle 3D canvas redraws to ~33 FPS and skip if Tab 2 is not visible."""
        if self._plot_redraw_job is not None:
            return
        self._plot_redraw_job = self.root.after(30, self._draw_regression_plot)

    def _reset_3d_view(self):
        self.cam_azim = math.radians(-52.0)
        self.cam_elev = math.radians(24.0)
        self._schedule_plot_redraw()

    def _on_plot_press(self, event):
        self._drag_last = (event.x, event.y)

    def _on_plot_drag(self, event):
        if self._drag_last is None:
            return
        dx = event.x - self._drag_last[0]
        dy = event.y - self._drag_last[1]
        if abs(dx) < 2 and abs(dy) < 2:
            return
        self._drag_last = (event.x, event.y)

        self.cam_azim += dx * 0.012
        self.cam_elev = max(math.radians(5.0), min(math.radians(80.0), self.cam_elev + dy * 0.012))
        self._schedule_plot_redraw()

    def _on_plot_release(self, _event):
        self._drag_last = None

    def _load_sample_data(self, silent: bool = False):
        """Load sample pumpkin launch trials to initialize the 3D plane regression."""
        sample_trials = [
            {"force": 42.0, "mass": 0.75, "range": 55.0},
            {"force": 48.0, "mass": 1.05, "range": 50.0},
            {"force": 74.0, "mass": 0.80, "range": 105.0},
            {"force": 82.0, "mass": 1.15, "range": 98.0},
            {"force": 122.0, "mass": 0.85, "range": 195.0},
            {"force": 135.0, "mass": 1.20, "range": 205.0},
            {"force": 172.0, "mass": 0.90, "range": 295.0},
            {"force": 188.0, "mass": 1.25, "range": 305.0},
        ]
        self.data_points = list(sample_trials)
        self._fit_plane_and_refresh()
        if not silent:
            messagebox.showinfo(
                "Sample Loaded",
                f"[OK] Loaded {len(sample_trials)} sample launch trials.",
            )

    def add_data_point(self):
        try:
            force = float(self.var_data_force.get())
            mass = float(self.var_data_mass.get())
            rng = float(self.var_data_range.get())

            if force <= 0 or mass <= 0 or rng <= 0:
                raise ValueError("Force, mass, and range must be positive values.")

            self.data_points.append({"force": force, "mass": mass, "range": rng})
            self.var_data_force.set("")
            self.var_data_mass.set("")
            self.var_data_range.set("")
            self._fit_plane_and_refresh()
        except ValueError as exc:
            messagebox.showwarning("Invalid Trial Data", f"Enter valid positive numbers.\n({exc})")

    def delete_selected_points(self):
        selected = self.tree_data.selection()
        if not selected:
            return
        indices = sorted(
            [int(self.tree_data.item(item, "values")[0]) - 1 for item in selected],
            reverse=True,
        )
        for idx in indices:
            if 0 <= idx < len(self.data_points):
                self.data_points.pop(idx)
        self._fit_plane_and_refresh()

    def clear_all_points(self):
        if not self.data_points:
            return
        if messagebox.askyesno("Confirm Clear", "Remove all recorded launch trials?"):
            self.data_points.clear()
            self._fit_plane_and_refresh()

    def import_csv(self):
        path = filedialog.askopenfilename(
            title="Import Launch Data CSV",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if not path:
            return
        try:
            loaded = []
            with open(path, mode="r", newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row or len(row) < 3:
                        continue
                    try:
                        force = float(row[0].strip())
                        mass = float(row[1].strip())
                        rng = float(row[2].strip())
                        loaded.append({"force": force, "mass": mass, "range": rng})
                    except ValueError:
                        continue
            if not loaded:
                raise ValueError("No valid (Force, Mass, Range) rows found in CSV.")
            self.data_points = loaded
            self._fit_plane_and_refresh()
            messagebox.showinfo("CSV Imported", f"[OK] Imported {len(loaded)} trials.")
        except Exception as exc:
            messagebox.showerror("Import Error", f"Failed to import CSV:\n{exc}")

    def export_csv(self):
        if not self.data_points:
            messagebox.showwarning("No Data", "No recorded trials available to export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export Launch Data CSV",
            defaultextension=".csv",
            initialfile="pumpkin_launch_data.csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Force_lbf", "Pumpkin_Mass_kg", "Launch_Range_ft"])
                for pt in self.data_points:
                    writer.writerow([pt["force"], pt["mass"], pt["range"]])
            messagebox.showinfo("CSV Exported", f"[OK] Saved {len(self.data_points)} trials to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export Error", f"Failed to export CSV:\n{exc}")

    @staticmethod
    def _solve_3x3(A, b_vec):
        """Solve 3x3 linear system A * x = b_vec via Gaussian elimination with partial pivoting."""
        M = [list(A[i]) + [b_vec[i]] for i in range(3)]
        for col in range(3):
            pivot_row = max(range(col, 3), key=lambda r: abs(M[r][col]))
            if abs(M[pivot_row][col]) < 1e-10:
                return None
            M[col], M[pivot_row] = M[pivot_row], M[col]
            pivot = M[col][col]
            for j in range(col, 4):
                M[col][j] /= pivot
            for r in range(3):
                if r != col:
                    factor = M[r][col]
                    for j in range(col, 4):
                        M[r][j] -= factor * M[col][j]
        return (M[0][3], M[1][3], M[2][3])

    def _fit_plane_and_refresh(self):
        """Fit a plane Force = a * Range + b * Mass + c using Ordinary Least Squares."""
        self.plane_coeffs = None
        r2_val = None
        rmse_val = None

        n = len(self.data_points)
        if n >= 3:
            ranges = [float(pt["range"]) for pt in self.data_points]
            masses = [float(pt["mass"]) for pt in self.data_points]
            forces = [float(pt["force"]) for pt in self.data_points]

            s_rr = sum(r * r for r in ranges)
            s_rm = sum(r * m for r, m in zip(ranges, masses))
            s_r = sum(ranges)
            s_mm = sum(m * m for m in masses)
            s_m = sum(masses)

            s_rf = sum(r * f for r, f in zip(ranges, forces))
            s_mf = sum(m * f for m, f in zip(masses, forces))
            s_f = sum(forces)

            xtx = [
                [s_rr, s_rm, s_r],
                [s_rm, s_mm, s_m],
                [s_r, s_m, float(n)],
            ]
            xty = [s_rf, s_mf, s_f]

            coeffs = self._solve_3x3(xtx, xty)
            if coeffs is not None:
                a, b, c = coeffs
                self.plane_coeffs = (a, b, c)

                preds = [a * r + b * m + c for r, m in zip(ranges, masses)]
                residuals = [f - p for f, p in zip(forces, preds)]
                ss_res = sum(res * res for res in residuals)
                mean_f = s_f / n
                ss_tot = sum((f - mean_f) ** 2 for f in forces)
                r2_val = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 1.0
                rmse_val = math.sqrt(ss_res / n)

        existing_children = self.tree_data.get_children()
        if existing_children:
            self.tree_data.delete(*existing_children)

        for idx, pt in enumerate(self.data_points, start=1):
            if self.plane_coeffs is not None:
                a, b, c = self.plane_coeffs
                pred = a * pt["range"] + b * pt["mass"] + c
                resid = pt["force"] - pred
                pred_str = f"{pred:.2f}"
                resid_str = f"{resid:+.2f}"
            else:
                pred_str = "--"
                resid_str = "--"

            self.tree_data.insert(
                "",
                tk.END,
                values=(
                    idx,
                    f"{pt['force']:.2f}",
                    f"{pt['mass']:.3f}",
                    f"{pt['range']:.1f}",
                    pred_str,
                    resid_str,
                ),
            )

        if self.plane_coeffs is not None:
            a, b, c = self.plane_coeffs
            sign_b = "+" if b >= 0 else "-"
            sign_c = "+" if c >= 0 else "-"
            self.lbl_plane_eq.config(
                text=f"FORCE = {a:.4f}*RANGE {sign_b} {abs(b):.4f}*MASS {sign_c} {abs(c):.4f}"
            )
            self.lbl_plane_stats.config(
                text=f"[FIT OK] N = {n}  |  R^2 = {r2_val:.4f}  |  RMSE = {rmse_val:.2f} LBF",
                style="StatusOkBg.TLabel",
            )
        else:
            if len(self.data_points) < 3:
                self.lbl_plane_eq.config(
                    text=f"[PENDING] MINIMUM 3 POINTS REQUIRED (CURRENT: {len(self.data_points)})"
                )
            else:
                self.lbl_plane_eq.config(
                    text="[ERROR] POINTS ARE COLLINEAR. ADD VARIED MASS AND RANGE DATA."
                )
            self.lbl_plane_stats.config(text="R^2 = --  |  RMSE = --", style="Muted.TLabel")

        self.predict_from_plane(silent=True)
        self._schedule_plot_redraw()
        self._schedule_save_state()

    def _schedule_pred_calc(self):
        if self._suppress_trace:
            return
        if self._pred_calc_job is not None:
            self.root.after_cancel(self._pred_calc_job)
        self._pred_calc_job = self.root.after(25, self._run_auto_predict)

    def _run_auto_predict(self):
        self._pred_calc_job = None
        self.predict_from_plane(silent=True)
        self._schedule_plot_redraw()
        self._schedule_save_state()

    def predict_from_plane(self, silent: bool = False):
        if self.plane_coeffs is None:
            self.lbl_pred_force.config(text="-- LBF")
            self.lbl_pred_sub.config(
                text="[WAITING] Fit plane with at least 3 non-collinear points.",
                style="StatusErr.TLabel",
            )
            self.tree_pred_all.item(self._pred_row_iid, values=("--", "--", "--", "--"))
            return

        try:
            target_range = float(self.var_pred_range.get())
            mass = float(self.var_pred_mass.get())
            if target_range <= 0 or mass <= 0:
                raise ValueError("Target range and pumpkin mass must be > 0.")

            a, b, c = self.plane_coeffs
            needed_force = a * target_range + b * mass + c
            needed_force_n = needed_force / es.newton_to_pound_force

            self.lbl_pred_force.config(text=f"{needed_force:.2f} LBF")
            self.lbl_pred_sub.config(
                text=f"[OK] {needed_force_n:.1f} N  |  TARGET RANGE: {target_range:g} FT  |  MASS: {mass:g} KG",
                style="StatusOk.TLabel",
            )

            self.tree_pred_all.item(
                self._pred_row_iid,
                values=tuple(f"{(a * r_ft + b * mass + c):.2f} LBF" for r_ft in (50.0, 100.0, 200.0, 300.0)),
            )

        except ValueError as exc:
            self.lbl_pred_force.config(text="-- LBF")
            self.lbl_pred_sub.config(text=f"[INPUT PENDING] {exc}", style="StatusErr.TLabel")
            self.tree_pred_all.item(self._pred_row_iid, values=("--", "--", "--", "--"))
            if not silent:
                messagebox.showwarning("Prediction Input Error", str(exc))

    def _draw_regression_plot(self):
        """Render an interactive 3D wireframe plot of the fitted plane (X=Range, Y=Mass, Z=Force)."""
        self._plot_redraw_job = None
        c = self.canvas_plot
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 120 or h < 120:
            return
        c.delete("all")

        r_min, r_max = 0.0, 320.0
        m_min, m_max = 0.4, 1.5
        f_min, f_max = 0.0, 220.0

        if self.data_points:
            r_max = max(r_max, max(pt["range"] for pt in self.data_points) * 1.08)
            m_min = min(m_min, min(pt["mass"] for pt in self.data_points) * 0.85)
            m_max = max(m_max, max(pt["mass"] for pt in self.data_points) * 1.12)
            f_max = max(f_max, max(pt["force"] for pt in self.data_points) * 1.15)

        try:
            user_r = float(self.var_pred_range.get())
            user_m = float(self.var_pred_mass.get())
            if user_r > 0:
                r_max = max(r_max, user_r * 1.08)
            if user_m > 0:
                m_min = min(m_min, user_m * 0.85)
                m_max = max(m_max, user_m * 1.12)
        except ValueError:
            user_r, user_m = 200.0, 0.9

        if self.plane_coeffs is not None:
            a, b, k = self.plane_coeffs
            corner_forces = [
                a * r_val + b * m_val + k
                for r_val in (r_min, r_max)
                for m_val in (m_min, m_max)
            ]
            f_max = max(f_max, max(corner_forces) * 1.1, 50.0)
            f_min = min(0.0, min(corner_forces))

        inv_r_span = 2.0 / max(1e-6, r_max - r_min)
        inv_m_span = 2.0 / max(1e-6, m_max - m_min)
        inv_f_span = 2.0 / max(1e-6, f_max - f_min)
        m_span = m_max - m_min
        r_span = r_max - r_min
        f_span = f_max - f_min

        cx = w * 0.50
        cy = h * 0.54
        scale = min(w, h) * 0.36

        cos_a = math.cos(self.cam_azim) * scale
        sin_a = math.sin(self.cam_azim) * scale
        cos_e = math.cos(self.cam_elev) * scale
        sin_e = math.sin(self.cam_elev)

        def project(r_val: float, m_val: float, f_val: float):
            nx = (r_val - r_min) * inv_r_span - 1.0
            ny = (m_val - m_min) * inv_m_span - 1.0
            nz = (f_val - f_min) * inv_f_span - 1.0

            sx = nx * cos_a - ny * sin_a
            ry_scaled = nx * sin_a + ny * cos_a
            sy = -nz * cos_e + ry_scaled * sin_e
            return cx + sx, cy + sy

        box_corners_bottom = [
            project(r_min, m_min, f_min),
            project(r_max, m_min, f_min),
            project(r_max, m_max, f_min),
            project(r_min, m_max, f_min),
        ]
        box_corners_top = [
            project(r_min, m_min, f_max),
            project(r_max, m_min, f_max),
            project(r_max, m_max, f_max),
            project(r_min, m_max, f_max),
        ]

        # Floor grid lines along Range (50, 100, 200, 300 ft)
        for r_tick in (50, 100, 200, 300):
            if r_min <= r_tick <= r_max:
                p1 = project(r_tick, m_min, f_min)
                p2 = project(r_tick, m_max, f_min)
                c.create_line(p1[0], p1[1], p2[0], p2[1], fill=BORDER_DARK, dash=(2, 3))
                c.create_text(
                    p1[0],
                    p1[1] + 12,
                    text=f"{r_tick}FT",
                    fill=TEXT_MUTED,
                    font=FONT_PLOT_SM,
                )

        # Floor grid lines along Mass
        m_steps = 3
        for i in range(m_steps + 1):
            m_tick = m_min + (m_span * i / m_steps)
            p1 = project(r_min, m_tick, f_min)
            p2 = project(r_max, m_tick, f_min)
            c.create_line(p1[0], p1[1], p2[0], p2[1], fill=BORDER_DARK, dash=(2, 3))
            c.create_text(
                p2[0] + 22,
                p2[1] + 4,
                text=f"{m_tick:.2f}KG",
                fill=TEXT_MUTED,
                font=FONT_PLOT_SM,
            )

        # Z-axis Force ticks on vertical origin pillar (r_min, m_min)
        z_steps = 4
        for i in range(z_steps + 1):
            f_tick = f_min + (f_span * i / z_steps)
            pz = project(r_min, m_min, f_tick)
            pz_end = project(r_max, m_min, f_tick)
            c.create_line(pz[0], pz[1], pz_end[0], pz_end[1], fill=BORDER_DARK, dash=(1, 4))
            c.create_text(
                pz[0] - 10,
                pz[1],
                text=f"{f_tick:.0f}",
                anchor=tk.E,
                fill=TEXT_MUTED,
                font=FONT_PLOT_SM,
            )

        # Wireframe outer cube edges
        for i in range(4):
            bx1, by1 = box_corners_bottom[i]
            bx2, by2 = box_corners_bottom[(i + 1) % 4]
            tx1, ty1 = box_corners_top[i]
            tx2, ty2 = box_corners_top[(i + 1) % 4]
            c.create_line(bx1, by1, bx2, by2, fill=BORDER_MID, width=1)
            c.create_line(tx1, ty1, tx2, ty2, fill=BORDER_DARK, width=1)
            c.create_line(bx1, by1, tx1, ty1, fill=BORDER_DARK, width=1)

        # Primary 3D Axes in Gold
        origin = box_corners_bottom[0]
        ax_r = box_corners_bottom[1]
        ax_m = box_corners_bottom[3]
        ax_f = box_corners_top[0]

        c.create_line(origin[0], origin[1], ax_r[0], ax_r[1], fill=MCC_GOLD, width=2)
        c.create_line(origin[0], origin[1], ax_m[0], ax_m[1], fill=MCC_GOLD, width=2)
        c.create_line(origin[0], origin[1], ax_f[0], ax_f[1], fill=MCC_GOLD, width=2)

        c.create_text(
            (origin[0] + ax_r[0]) * 0.5,
            (origin[1] + ax_r[1]) * 0.5 + 24,
            text="X: RANGE (FT)",
            fill=MCC_GOLD,
            font=FONT_PLOT_MD,
        )
        c.create_text(
            ax_m[0] - 12,
            ax_m[1] + 16,
            text="Y: MASS (KG)",
            fill=MCC_GOLD,
            font=FONT_PLOT_MD,
        )
        c.create_text(
            ax_f[0] - 8,
            ax_f[1] - 14,
            text="Z: FORCE (LBF)",
            fill=MCC_GOLD,
            font=FONT_PLOT_MD,
        )

        # 2. Draw Fitted 3D Plane Surface Mesh (planar lines need only 2 endpoints!)
        if self.plane_coeffs is not None:
            a, b, k = self.plane_coeffs
            grid_r = 6
            grid_m = 4

            for j in range(grid_m + 1):
                m_val = m_min + (m_span * j / grid_m)
                p_start = project(r_min, m_val, a * r_min + b * m_val + k)
                p_end = project(r_max, m_val, a * r_max + b * m_val + k)
                line_color = MCC_GOLD if j in (0, grid_m) else BORDER_MID
                c.create_line(p_start[0], p_start[1], p_end[0], p_end[1], fill=line_color, width=1)

            for i in range(grid_r + 1):
                r_val = r_min + (r_span * i / grid_r)
                p_start = project(r_val, m_min, a * r_val + b * m_min + k)
                p_end = project(r_val, m_max, a * r_val + b * m_max + k)
                line_color = MCC_GOLD if i in (0, grid_r) else BORDER_MID
                c.create_line(p_start[0], p_start[1], p_end[0], p_end[1], fill=line_color, width=1)

            for r_std in (50.0, 100.0, 200.0, 300.0):
                if r_min <= r_std <= r_max:
                    p_start = project(r_std, m_min, a * r_std + b * m_min + k)
                    p_end = project(r_std, m_max, a * r_std + b * m_max + k)
                    c.create_line(
                        p_start[0],
                        p_start[1],
                        p_end[0],
                        p_end[1],
                        fill=MCC_GOLD,
                        width=2,
                        dash=(4, 2),
                    )

        # 3. Draw Empirical Data Points in 3D + Residual Segments to Plane
        for pt in self.data_points:
            px, py = project(pt["range"], pt["mass"], pt["force"])
            if self.plane_coeffs is not None:
                a, b, k = self.plane_coeffs
                f_hat = a * pt["range"] + b * pt["mass"] + k
                hx, hy = project(pt["range"], pt["mass"], f_hat)
                c.create_line(px, py, hx, hy, fill=TEXT_MUTED, dash=(2, 2))
                c.create_rectangle(hx - 2, hy - 2, hx + 2, hy + 2, fill=MCC_GOLD, outline=MCC_GOLD)

            c.create_rectangle(
                px - 4,
                py - 4,
                px + 4,
                py + 4,
                fill=TEXT_WHITE,
                outline=MCC_GOLD,
                width=1,
            )

        # 4. Highlight Selected Target Prediction Point on the 3D Plane
        if self.plane_coeffs is not None:
            try:
                target_r = float(self.var_pred_range.get())
                target_m = float(self.var_pred_mass.get())
                if target_r > 0 and target_m > 0:
                    a, b, k = self.plane_coeffs
                    pred_f = a * target_r + b * target_m + k

                    tx, ty = project(target_r, target_m, pred_f)
                    floor_x, floor_y = project(target_r, target_m, f_min)

                    c.create_line(tx, ty, floor_x, floor_y, fill=SUCCESS_GREEN, width=2, dash=(3, 3))
                    c.create_rectangle(
                        tx - 6,
                        ty - 6,
                        tx + 6,
                        ty + 6,
                        fill=SUCCESS_GREEN,
                        outline=BG_MAIN,
                        width=1,
                    )
                    c.create_text(
                        tx + 10,
                        ty - 10,
                        text=f"[{target_r:g}FT, {target_m:g}KG -> {pred_f:.1f}LBF]",
                        anchor=tk.W,
                        fill=SUCCESS_GREEN,
                        font=FONT_PLOT_MD,
                    )
            except ValueError:
                pass


def main():
    root = tk.Tk()
    PumpkinLauncherGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
