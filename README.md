# ELC Pumpkin Launcher 2026 - Force Calculator & 3D Plane Regression

An offline-ready **Web / Mobile / iPad PWA (GitHub Pages)** and **Python Desktop GUI** calculator and empirical 3D plane regression tool for the **Engineering Leadership Council (ELC) Pumpkin Launcher (2026)**.

Built with the MCC ELC dark-and-gold terminal aesthetic, zero external dependencies, and optimized to run smoothly on mobile phones, iPads, and low-spec hardware like a Raspberry Pi.

---

## Features

1. **`[1] PHYSICS MODEL` (Aerodynamic & Elastic Band Math Model)**
   - **Real-Time Automatic Calculation**: Enter the non-constant launch parameters and see the required pullback force (`LBF` and `N`), draw distance $d$, and stretch ratio $S_r$ update automatically as you type:
     - **Pumpkin Mass $m_p$ (`kg`)**
     - **Efficiency $n$ (`0` to `1`)**
     - **Band Count $B$**
     - **Target Range $R$ (`ft`)** - includes quick-select buttons for `50FT`, `100FT`, `200FT`, and `300FT` as well as custom range input.
   - **Target Range Matrix**: Simultaneously displays vacuum velocity $v_{\text{vac}}$, initial velocity with drag $v_0$, draw distance $d$, stretch ratio $S_r$, and required pullback force across all four standard distances (`50 ft`, `100 ft`, `200 ft`, `300 ft`).
   - **Intermediate Physics Breakdown**: Displays all intermediate quantities in real time.

2. **`[2] 3D PLANE REGRESSION` (Empirical Linear Regression)**
   - **Trial Data Management**: Record actual field trials consisting of **Pullback Force (`lbf`)**, **Pumpkin Mass (`kg`)**, and **Measured Launch Range (`ft`)**.
   - **3D Least-Squares Plane Fit**: Fits a 3D plane using Gaussian elimination with partial pivoting (zero third-party packages required):
     $$\text{Force} = a \cdot \text{Range} + b \cdot \text{Mass} + c$$
   - **Fit Diagnostics**: Displays the fitted plane equation, sample count $N$, coefficient of determination $R^2$, root-mean-square error ($\text{RMSE}$), and per-trial residuals.
   - **Real-Time Force Prediction**: Select a desired range (`50FT`, `100FT`, `200FT`, `300FT`, or custom) and enter the pumpkin mass (`kg`) to immediately see the required pullback force (`LBF` and `N`) along with a 4-target summary row.
   - **Interactive 3D Wireframe Plot**: Displays the fitted 3D plane (`X = Range`, `Y = Mass`, `Z = Force`), target range contour lines, recorded 3D trial points with residual drop-lines, and the active target prediction marker. Touch or drag anywhere on the canvas to orbit in 3D.

3. **`[3] LAUNCHER SETTINGS (CONSTANTS)`**
   - Edit all physical constants of the launcher (`SLING_MASS`, `BAND_STRENGTH`, `BAND_REST_LENGTH`, `LAUNCH_ANGLE`, `GRAVITY`, `DRAG_COEFFICIENT`, `AIR_DENSITY`, `PUMPKIN_DENSITY`, and `NEWTON_TO_LBF`) with live validation and a one-click reset to defaults.

4. **Automatic Offline Data Persistence + GitHub Cloud Sync (`.csv` & `.json`)**
   - **Web / Mobile / iPad App**:
     - Always saves all inputs, constants, and trial points immediately to local device storage (`localStorage`), plus one-tap **Export/Import CSV (`pumpkin_launch_data.csv`)** and **Export/Import JSON (`launcher_state.json`)**.
     - **Built-in GitHub Repository Sync**: Can **Pull** the latest `pumpkin_launch_data.csv` and `launcher_state.json` directly from your GitHub repository, and **Save / Commit** updated trials and state straight back to your GitHub repository from an iPad or phone (automatically or via the `SAVE TO GITHUB` button).
   - **Python Desktop App (`gui.py`)**: Automatically saves and reloads `pumpkin_launch_data.csv` and `launcher_state.json` in the project folder using the exact same file format.

---

## Deploying to GitHub Pages & Syncing Data Across Devices

### 1. Enable GitHub Pages
1. Push this repository to GitHub.
2. In your GitHub repository, go to **Settings -> Pages**.
3. Under **Build and deployment**, set **Source** to **Deploy from a branch**, select your main branch (`main` or `master`) and `/ (root)`, and click **Save**.
4. Your app will be live at `https://<your-username>.github.io/<repo-name>/` with zero build step required.

### 2. Configure GitHub Cloud Sync (Save Data from iPad / Phone to GitHub)
1. On GitHub, go to **Settings -> Developer settings -> Personal access tokens -> Fine-grained tokens** (or Classic tokens).
2. Generate a token scoped to your Pumpkin Launcher repository with **Repository permissions -> Contents: Read and write**.
3. Open your GitHub Pages site on your iPad, phone, or laptop and go to **Tab `[3] LAUNCHER SETTINGS & GITHUB SYNC`**.
4. Confirm the **GITHUB REPO (`owner/repo`)** and **BRANCH (`main`)**, and paste your token into **GITHUB ACCESS TOKEN (PAT)**.
   - Your token is stored **only** in that device's private `localStorage` and is never written into `launcher_state.json` or committed to the repository.
5. Whenever you add or edit trial data on your iPad/phone (or tap **`SAVE TO GITHUB`**), the app automatically commits the updated `pumpkin_launch_data.csv` and `launcher_state.json` directly to your GitHub repository.
6. Anyone else on the team can tap **`PULL FROM GITHUB`** to immediately load the latest trials and settings.

### 3. Install on iPad / iPhone / Android (Offline Home Screen App)
- **iPad / iPhone (Safari)**: Open the GitHub Pages URL in Safari, tap the **Share** button, and tap **Add to Home Screen**.
- **Android (Chrome)**: Open the URL in Chrome, tap the menu, and select **Add to Home Screen / Install App**.
- Because of the built-in Service Worker (`sw.js`) and Web App Manifest (`manifest.json`), the installed app caches all files on the device and runs **100% offline** in the field.

### 3. Run the Web App Locally
```bash
python -m http.server 8000
```
Then open `http://localhost:8000` in any browser.

---

## Running the Python Desktop App (Windows / Raspberry Pi)

### Launch Desktop GUI
```bash
python gui.py
```

### Run Standalone CLI Physics Script
```bash
python equation_solver.py
```

---

## Project Architecture

```text
.
|-- index.html                  # GitHub Pages / Mobile / iPad responsive web entrypoint
|-- styles.css                  # ELC dark & gold theme stylesheet with mobile/iPad breakpoints
|-- manifest.json               # PWA Web App Manifest for iPad/mobile home-screen install
|-- sw.js                       # Offline Service Worker caching all web assets
|-- icon.svg                    # Vector app icon for iOS/iPadOS/Android home screen
|-- js/
|   |-- app.js                  # Main web UI controller & auto-calculation bindings
|   |-- physics.js              # Aerodynamic + elastic band physics model module
|   |-- regression.js           # 3x3 Gaussian elimination & 3D least-squares plane solver
|   |-- plot3d.js               # Touch/pointer interactive 3D wireframe canvas renderer
|   `-- storage.js              # Offline localStorage + CSV/JSON + GitHub sync utilities
|-- gui.py                      # Offline Python Tkinter desktop GUI (Windows / Raspberry Pi)
|-- equation_solver.py          # Standalone Python physics equation solver
|-- pumpkin_launch_data.csv     # Auto-saved CSV of recorded empirical launch trials
`-- launcher_state.json         # Auto-saved JSON state of inputs, constants, and trials
```
