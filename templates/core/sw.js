/*
 * Service worker : rend le site installable et montre une page « Hors ligne » sans réseau.
 * Les pages ne sont JAMAIS mises en cache : l'espace des membres est derrière le code
 * d'accès, et un téléphone partagé ne doit pas l'afficher à quelqu'un d'autre. Seuls les
 * fichiers statiques (noms versionnés, donc immuables) et la page hors ligne le sont.
 */
const CACHE = "collectif-{{ version }}";
const OFFLINE = "{{ offline_url|escapejs }}";
const STATIC_PREFIX = "{{ static_prefix|escapejs }}";
const PRECACHE = [{% for url in precache %}"{{ url|escapejs }}"{% if not forloop.last %}, {% endif %}{% endfor %}];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    // Toujours le réseau ; la page hors ligne seulement s'il ne répond pas.
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE)));
    return;
  }
  if (url.pathname.startsWith(STATIC_PREFIX)) {
    event.respondWith(
      caches.match(request).then((hit) => hit || fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      }))
    );
  }
});
