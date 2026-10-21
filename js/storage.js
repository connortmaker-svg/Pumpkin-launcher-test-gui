const STORAGE_KEY = "ELC_PUMPKIN_LAUNCHER_2026_STATE_V1";
const GH_CONFIG_KEY = "ELC_PUMPKIN_LAUNCHER_2026_GH_CONFIG_V1";
const DEFAULT_REPO = "connortmaker-svg/Pumpkin-launcher-test-gui";

export function detectDefaultGitHubRepo() {
  try {
    const host = window.location.hostname || "";
    const pathParts = (window.location.pathname || "").split("/").filter(Boolean);
    if (host.endsWith(".github.io")) {
      const owner = host.replace(/\.github\.io$/i, "");
      const repo = pathParts[0] || "";
      if (owner && repo) {
        return `${owner}/${repo}`;
      }
    }
  } catch (_err) {}
  return DEFAULT_REPO;
}

export function loadGitHubConfig() {
  const fallback = {
    repo: detectDefaultGitHubRepo(),
    branch: "main",
    token: "",
    autoSync: true,
  };
  let cfg = { ...fallback };
  try {
    const raw = localStorage.getItem(GH_CONFIG_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      cfg = {
        repo: parsed.repo || fallback.repo,
        branch: parsed.branch || "main",
        token: parsed.token || "",
        autoSync: parsed.autoSync !== undefined ? Boolean(parsed.autoSync) : true,
      };
    }
  } catch (_err) {}

  try {
    const params = new URLSearchParams(window.location.search);
    const urlToken = (params.get("token") || "").trim();
    const urlRepo = (params.get("repo") || "").trim();
    const urlBranch = (params.get("branch") || "").trim();
    if (urlToken || urlRepo || urlBranch) {
      if (urlToken) cfg.token = urlToken;
      if (urlRepo) cfg.repo = urlRepo;
      if (urlBranch) cfg.branch = urlBranch;
      saveGitHubConfig(cfg);
      params.delete("token");
      params.delete("repo");
      params.delete("branch");
      const qs = params.toString();
      const cleanUrl = window.location.pathname + (qs ? `?${qs}` : "") + window.location.hash;
      window.history.replaceState({}, document.title, cleanUrl);
    }
  } catch (_err) {}

  return cfg;
}

export function saveGitHubConfig(cfg) {
  try {
    localStorage.setItem(
      GH_CONFIG_KEY,
      JSON.stringify({
        repo: (cfg.repo || "").trim(),
        branch: (cfg.branch || "main").trim() || "main",
        token: (cfg.token || "").trim(),
        autoSync: Boolean(cfg.autoSync),
      })
    );
  } catch (_err) {}
}

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
  } catch (_err) {}
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

function utf8ToBase64(str) {
  const bytes = new TextEncoder().encode(str);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function base64ToUtf8(b64) {
  const clean = b64.replace(/\s+/g, "");
  const binary = atob(clean);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new TextDecoder().decode(bytes);
}

export async function pullStateFromGitHub(ghConfig) {
  const repo = (ghConfig.repo || "").trim();
  const branch = (ghConfig.branch || "main").trim() || "main";
  const token = (ghConfig.token || "").trim();

  if (repo && repo.includes("/")) {
    const headers = { Accept: "application/vnd.github.v3+json" };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const stateUrl = `https://api.github.com/repos/${repo}/contents/launcher_state.json?ref=${encodeURIComponent(branch)}&t=${Date.now()}`;
    const res = await fetch(stateUrl, { headers, cache: "no-store" });
    if (!res.ok) {
      throw new Error(`GitHub pull failed (${res.status} ${res.statusText})`);
    }
    const data = await res.json();
    const stateJson = JSON.parse(base64ToUtf8(data.content));

    try {
      const csvUrl = `https://api.github.com/repos/${repo}/contents/pumpkin_launch_data.csv?ref=${encodeURIComponent(branch)}&t=${Date.now()}`;
      const csvRes = await fetch(csvUrl, { headers, cache: "no-store" });
      if (csvRes.ok) {
        const csvData = await csvRes.json();
        const trials = parseTrialsCSV(base64ToUtf8(csvData.content));
        if (trials.length > 0) {
          stateJson.data_points = trials;
        }
      }
    } catch (_err) {}

    return stateJson;
  }

  const localRes = await fetch(`./launcher_state.json?t=${Date.now()}`, { cache: "no-store" });
  if (!localRes.ok) {
    throw new Error("Could not fetch launcher_state.json from server.");
  }
  return await localRes.json();
}

async function upsertGitHubFile(repo, branch, token, filePath, textContent, commitMessage) {
  const apiUrl = `https://api.github.com/repos/${repo}/contents/${filePath}`;
  const headers = {
    Accept: "application/vnd.github.v3+json",
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };

  let sha = null;
  const getRes = await fetch(`${apiUrl}?ref=${encodeURIComponent(branch)}&t=${Date.now()}`, {
    headers,
    cache: "no-store",
  });
  if (getRes.ok) {
    const existing = await getRes.json();
    sha = existing.sha;
  } else if (getRes.status !== 404) {
    const errBody = await getRes.text();
    throw new Error(`GitHub read error (${getRes.status}): ${errBody}`);
  }

  const body = {
    message: commitMessage,
    content: utf8ToBase64(textContent),
    branch,
  };
  if (sha) {
    body.sha = sha;
  }

  const putRes = await fetch(apiUrl, {
    method: "PUT",
    headers,
    body: JSON.stringify(body),
  });

  if (!putRes.ok) {
    let detail = putRes.statusText;
    try {
      const errJson = await putRes.json();
      if (errJson && errJson.message) detail = errJson.message;
    } catch (_e) {}
    throw new Error(`GitHub commit failed (${putRes.status}): ${detail}`);
  }
}

export async function pushStateToGitHub(ghConfig, state) {
  const repo = (ghConfig.repo || "").trim();
  const branch = (ghConfig.branch || "main").trim() || "main";
  const token = (ghConfig.token || "").trim();

  if (!repo || !repo.includes("/")) {
    throw new Error("Set GitHub Repo (owner/repo) in Tab [3] Settings.");
  }
  if (!token) {
    throw new Error("Set GitHub Personal Access Token in Tab [3] Settings to push changes.");
  }

  const csvContent = formatTrialsCSV(state.data_points || []);
  const jsonContent = JSON.stringify(state, null, 2) + "\n";
  const timestamp = new Date().toISOString().replace("T", " ").slice(0, 19) + " UTC";

  await upsertGitHubFile(
    repo,
    branch,
    token,
    "pumpkin_launch_data.csv",
    csvContent,
    `Update pumpkin_launch_data.csv (${timestamp})`
  );

  await upsertGitHubFile(
    repo,
    branch,
    token,
    "launcher_state.json",
    jsonContent,
    `Update launcher_state.json (${timestamp})`
  );
}
