/*
 * Grand écran (/p/affichage/) : l'horloge avance, le contenu est redemandé chaque minute,
 * donc un nouvel événement apparaît et le jour change à minuit sans que personne ne touche
 * l'écran. Si le serveur ne répond pas, on garde l'affichage et on réessaie.
 */
(function () {
  "use strict";
  const board = document.getElementById("tableau");
  const configNode = document.getElementById("board-config");
  if (!board || !configNode) return;
  const config = JSON.parse(configNode.textContent);
  const clock = document.getElementById("horloge");
  const status = document.getElementById("etat");
  const fullscreen = document.getElementById("plein-ecran");

  const REFRESH_MS = 60 * 1000;
  // Recharger toute la page de temps en temps : après une mise en ligne, l'écran prend
  // les nouveaux fichiers. Seulement si le serveur vient de répondre, sinon l'écran
  // afficherait une page d'erreur et ne se relancerait plus.
  const RELOAD_MS = 6 * 60 * 60 * 1000;
  const loadedAt = Date.now();
  const timeFormat = new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: config.timeZone,
  });
  let lastHtml = board.innerHTML.trim();

  function tick() {
    if (clock) clock.textContent = timeFormat.format(new Date());
  }

  async function refresh() {
    try {
      const response = await fetch(config.fragmentUrl, {
        cache: "no-store",
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error(String(response.status));
      const html = (await response.text()).trim();
      if (Date.now() - loadedAt > RELOAD_MS) {
        window.location.reload();
        return;
      }
      if (html !== lastHtml) {
        board.innerHTML = html;
        lastHtml = html;
      }
      if (status) {
        status.textContent = "";
        status.classList.remove("board__status--lost");
      }
    } catch (error) {
      if (status) {
        status.textContent = `Connexion perdue depuis ${timeFormat.format(new Date())}, nouvel essai chaque minute.`;
        status.classList.add("board__status--lost");
      }
    }
  }

  // L'écran reste allumé (tablette, téléviseur avec navigateur) quand le navigateur le permet.
  let wakeLock = null;
  async function keepAwake() {
    if (!("wakeLock" in navigator) || document.visibilityState !== "visible") return;
    try {
      wakeLock = await navigator.wakeLock.request("screen");
    } catch (error) {
      wakeLock = null; // refusé ou non pris en charge : l'écran suit ses propres réglages
    }
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      if (!wakeLock || wakeLock.released) keepAwake();
      refresh();
    }
  });

  // Plein écran : un clic suffit, le bouton disparaît ensuite.
  if (fullscreen && document.documentElement.requestFullscreen) {
    const sync = () => {
      fullscreen.hidden = Boolean(document.fullscreenElement);
    };
    fullscreen.addEventListener("click", () => {
      document.documentElement.requestFullscreen().catch(() => {});
    });
    document.addEventListener("fullscreenchange", sync);
    sync();
  }

  // Le pointeur s'efface quand la souris ne bouge plus.
  let idleTimer = null;
  document.addEventListener("mousemove", () => {
    document.body.classList.remove("board--idle");
    window.clearTimeout(idleTimer);
    idleTimer = window.setTimeout(() => document.body.classList.add("board--idle"), 4000);
  });

  tick();
  keepAwake();
  window.setInterval(tick, 1000);
  window.setInterval(refresh, REFRESH_MS);
})();
