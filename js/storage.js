// =============================================================================
// ELC PUMPKIN LAUNCHER 2026 - OFFLINE STORAGE & CSV / JSON PERSISTENCE MODULE
// =============================================================================

const STORAGE_KEY = "ELC_PUMPKIN_LAUNCHER_2026_STATE_V1";

export function loadSavedState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (_err) {
    return null;
  }
}

export function saveStateToStorage(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (_err) {
    // Ignore storage quota or private mode errors
  }
}

export function formatTrialsCSV(dataPoints) {
  const lines = ["Force_lbf,Pumpkin_Mass_kg,Launch_Range_ft"];
  for (let i = 0; i < dataPoints.length; i++) {
    const pt = dataPoints[i];
    lines.push(`${pt.force},${pt.mass},${pt.range}`);
  }
  return lines.join("\n") + "\n";
}

export function parseTrialsCSV(csvText) {
  const lines = csvText.split(/\r?\n/);
  const loaded = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const parts = line.split(",");
    if (parts.length < 3) continue;
    const force = Number(parts[0].trim());
    const mass = Number(parts[1].trim());
    const range = Number(parts[2].trim());
    if (Number.isFinite(force) && Number.isFinite(mass) && Number.isFinite(range)) {
      if (force > 0 && mass > 0 && range > 0) {
        loaded.push({ force, mass, range });
      }
    }
  }
  return loaded;
}

export function downloadTextFile(filename, content, mimeType = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
