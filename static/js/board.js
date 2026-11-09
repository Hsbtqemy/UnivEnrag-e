/*
 * Grand écran (/p/affichage/) : les vues tournent (aujourd'hui, 7 jours, le mois), un
 * bouton par vue permet d'y passer directement, « Réglages » choisit les vues, leur durée
 * et les couleurs. Une journée trop chargée passe page par page, l'horloge avance et le
 * contenu est redemandé
 * chaque minute. Un nouvel événement apparaît et le jour change à minuit sans que
 * personne ne touche l'écran. Si le serveur ne répond pas, on garde l'affichage.
 */
(function () {
  "use strict";
  const board = document.getElementById("tableau");
  const configNode = document.getElementById("board-config");
  if (!board || !configNode) return;
  const config = JSON.parse(configNode.textContent);
  const clock = document.getElementById("horloge");
  const status = document.getElementById("etat");
  const indicator = document.getElementById("vues");
  const fullscreen = document.getElementById("plein-ecran");
  const settings = document.getElementById("reglages");
  const footer = document.querySelector(".board__foot");

  const REFRESH_MS = 60 * 1000;
  const VIEW_MS = config.duration * 1000;
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
  let pendingHtml = null; // nouveau contenu, posé au prochain changement de vue
  let currentView = null;
  let pages = [];
  let pageIndex = 0;
  let rotation = null;

  function tick() {
    if (clock) clock.textContent = timeFormat.format(new Date());
  }

  // --- Vues ------------------------------------------------------------------------------

  function activePanels() {
    return Array.from(board.querySelectorAll("[data-view]")).filter(
      (panel) => config.views.includes(panel.dataset.view) && !panel.hasAttribute("data-empty"),
    );
  }

  // Un bouton par vue : on passe directement à celle qu'on veut, la rotation reprend
  // ensuite depuis elle.
  function renderIndicator(panels) {
    if (!indicator) return;
    indicator.replaceChildren();
    indicator.hidden = panels.length < 2;
    panels.forEach((panel) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.goto = panel.dataset.view;
      button.textContent = config.labels[panel.dataset.view];
      if (panel.dataset.view === currentView) {
        item.className = "is-current";
        button.setAttribute("aria-current", "true");
      }
      item.append(button);
      indicator.append(item);
    });
  }

  if (indicator) {
    indicator.addEventListener("click", (event) => {
      const button = event.target.closest("[data-goto]");
      if (!button) return;
      show(button.dataset.goto);
      schedule();
      const current = indicator.querySelector("[aria-current]");
      if (current) current.focus();
    });
  }

  // Découpe une liste trop longue pour sa place en pages d'éléments entiers.
  function paginate(list) {
    const items = Array.from(list.children);
    items.forEach((item) => {
      item.hidden = false;
    });
    const room = list.clientHeight;
    if (!items.length || list.scrollHeight <= room + 1) return [items];
    const result = [];
    let page = [];
    let pageTop = items[0].offsetTop;
    items.forEach((item) => {
      const bottom = item.offsetTop + item.offsetHeight - pageTop;
      if (page.length && bottom > room) {
        result.push(page);
        page = [];
        pageTop = item.offsetTop;
      }
      page.push(item);
    });
    result.push(page);
    return result;
  }

  // Un bloc trop rempli pour sa place (un jour de la semaine, une case du mois, « À
  // venir ») : on masque ses derniers éléments, et « + N autres » les compte.
  function fit(container) {
    const units = Array.from(container.querySelectorAll(container.dataset.fit));
    const more = container.querySelector("[data-more]");
    const base = more ? Number(more.dataset.more) || 0 : 0;
    let hidden = 0;
    const label = () => {
      if (!more) return;
      const n = base + hidden;
      more.hidden = n === 0;
      more.textContent = more.hasAttribute("data-short") ? `+ ${n}` : `+ ${n} autre${n > 1 ? "s" : ""}`;
    };
    units.forEach((unit) => {
      unit.hidden = false;
    });
    label();
    for (let i = units.length - 1; i > 0 && container.scrollHeight > container.clientHeight + 1; i--) {
      units[i].hidden = true;
      hidden += 1;
      label();
    }
  }

  function showPage(panel) {
    const list = panel.querySelector("[data-paginate]");
    const pager = panel.querySelector("[data-pager]");
    if (list && pages.length > 1) {
      Array.from(list.children).forEach((item) => {
        item.hidden = !pages[pageIndex].includes(item);
      });
    }
    if (pager) pager.textContent = pages.length > 1 ? `${pageIndex + 1}/${pages.length}` : "";
  }

  function show(view) {
    if (pendingHtml !== null) {
      board.innerHTML = pendingHtml;
      lastHtml = pendingHtml;
      pendingHtml = null;
    }
    let panels = activePanels();
    // Rien à montrer dans les vues demandées : la journée, toujours présente.
    if (!panels.length) panels = [board.querySelector('[data-view="jour"]')].filter(Boolean);
    if (!panels.length) return;
    const panel = panels.find((p) => p.dataset.view === view) || panels[0];
    currentView = panel.dataset.view;
    board.querySelectorAll("[data-view]").forEach((p) => {
      p.hidden = p !== panel;
    });
    panel.querySelectorAll("[data-fit]").forEach(fit);
    const list = panel.querySelector("[data-paginate]");
    pages = list ? paginate(list) : [[]];
    pageIndex = 0;
    showPage(panel);
    renderIndicator(panels);
  }

  function next() {
    if (pageIndex + 1 < pages.length) {
      pageIndex += 1;
      const panel = board.querySelector(`[data-view="${currentView}"]`);
      if (panel) showPage(panel);
    } else {
      const panels = activePanels();
      const position = panels.findIndex((p) => p.dataset.view === currentView);
      const following = panels[(position + 1) % panels.length];
      show(following ? following.dataset.view : null);
    }
    schedule();
  }

  function schedule() {
    window.clearTimeout(rotation);
    rotation = window.setTimeout(next, VIEW_MS);
  }

  // --- Rafraîchissement ------------------------------------------------------------------

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
      if (html !== lastHtml) pendingHtml = html;
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

  // --- Écran -----------------------------------------------------------------------------

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

  // Plein écran : un clic suffit, le bouton disparaît ensuite. Le découpage en pages
  // dépend de la hauteur : on le refait quand elle change.
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
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => show(currentView), 300);
  });

  // Le pointeur et les commandes (réglages, plein écran) s'effacent quand personne ne
  // touche l'écran ; ils reviennent au moindre mouvement, toucher ou appui sur une touche.
  // Pas tant que les réglages sont ouverts ou qu'une commande a le focus.
  let idleTimer = null;
  function goIdle() {
    const busy = (settings && settings.open) || (footer && footer.contains(document.activeElement));
    if (busy) {
      idleTimer = window.setTimeout(goIdle, 4000);
      return;
    }
    document.body.classList.add("board--idle");
  }
  function wake() {
    document.body.classList.remove("board--idle");
    window.clearTimeout(idleTimer);
    idleTimer = window.setTimeout(goIdle, 4000);
  }
  ["mousemove", "pointerdown", "keydown"].forEach((name) => {
    document.addEventListener(name, wake, { passive: true });
  });

  tick();
  keepAwake();
  wake();
  show(config.views[0]);
  schedule();
  window.setInterval(tick, 1000);
  window.setInterval(refresh, REFRESH_MS);
})();
