const CACHE_NAME = "liza-pwa-v9";
const APP_FILES = [
    "./",
    "./index.html",
    "./style.css?v=20261001-micdock",
    "./orb-particles.js",
    "./assistant-client.js?v=20261001-session9",
    "./manifest.webmanifest",
    "./assets/img/pwa-192.png",
    "./assets/img/pwa-512.png"
];

self.addEventListener("install", function (event) {
    event.waitUntil(caches.open(CACHE_NAME).then(function (cache) {
        return cache.addAll(APP_FILES);
    }));
    self.skipWaiting();
});

self.addEventListener("activate", function (event) {
    event.waitUntil(caches.keys().then(function (keys) {
        return Promise.all(keys.filter(function (key) {
            return key !== CACHE_NAME;
        }).map(function (key) {
            return caches.delete(key);
        }));
    }));
    self.clients.claim();
});

self.addEventListener("fetch", function (event) {
    var request = event.request;
    var url = new URL(request.url);
    if (request.method !== "GET" || url.origin !== self.location.origin) return;
    if (url.pathname.indexOf("/api/") === 0) return;

    if (request.mode === "navigate") {
        event.respondWith(fetch(request).then(function (response) {
            var copy = response.clone();
            caches.open(CACHE_NAME).then(function (cache) {
                cache.put(request, copy);
            });
            return response;
        }).catch(function () {
            return caches.match(request).then(function (cached) {
                return cached || caches.match("./");
            });
        }));
        return;
    }

    event.respondWith(fetch(request).then(function (response) {
        if (response.ok) {
            var copy = response.clone();
            caches.open(CACHE_NAME).then(function (cache) {
                cache.put(request, copy);
            });
        }
        return response;
    }).catch(function () {
        return caches.match(request);
    }));
});
