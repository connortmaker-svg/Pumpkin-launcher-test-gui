const CACHE_NAME = "elc-pumpkin-launcher-2026-v2";
const ASSETS = [
  "./",
  "./index.html",
  "./styles.css",
  "./manifest.json",
  "./icon.svg",
  "./js/app.js",
  "./js/physics.js",
  "./js/regression.js",
  "./js/plot3d.js",
  "./js/storage.js",
  "./launcher_state.json",
  "./pumpkin_launch_data.csv",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);

  // Always use network directly for GitHub REST API requests
  if (url.hostname === "api.github.com") {
    return;
  }

  // Network-first for data files (launcher_state.json / pumpkin_launch_data.csv), fallback to cache offline
  if (url.pathname.endsWith("launcher_state.json") || url.pathname.endsWith("pumpkin_launch_data.csv")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(url.pathname))
    );
    return;
  }

  // Cache-first for static app shell assets, fallback to network
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match("./index.html"));
    })
  );
});
