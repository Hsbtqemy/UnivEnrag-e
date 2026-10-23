/*
 * Mode d'affichage : clair, sombre ou « Enragé » (rouge braise). Par défaut, celui du
 * système (clair ou sombre) ; chaque clic sur le bouton de l'en-tête passe au suivant,
 * retenu par ce navigateur seulement (stockage local, ni cookie ni serveur). Chargé dans
 * <head>, avant la feuille de style : pas de clignotement.
 */
(function () {
  "use strict";
  const KEY = "theme";
  const ORDER = ["light", "dark", "enrage"];
  const LABELS = { light: "Mode clair", dark: "Mode sombre", enrage: "Mode enragé" };
  const COLORS = { light: "#2f5d8c", dark: "#15171a", enrage: "#5c0f0b" };
  const root = document.documentElement;
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)");

  function read() {
    try {
      return window.localStorage.getItem(KEY);
    } catch (error) {
      return null; // navigation privée, stockage bloqué : on suit le système
    }
  }

  function write(value) {
    try {
      window.localStorage.setItem(KEY, value);
    } catch (error) {
      // le choix vaut alors pour cette page seulement
    }
  }

  const saved = read();
  if (ORDER.includes(saved)) root.dataset.theme = saved;

  function current() {
    return root.dataset.theme || (systemDark.matches ? "dark" : "light");
  }

  function next() {
    return ORDER[(ORDER.indexOf(current()) + 1) % ORDER.length];
  }

  document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("bouton-theme");
    if (!button) return;
    const meta = document.querySelector('meta[name="theme-color"]');
    const sync = () => {
      const label = `${LABELS[current()]} (passer au ${LABELS[next()].toLowerCase()})`;
      button.dataset.next = next();
      button.setAttribute("aria-label", label);
      button.title = label;
      if (meta) meta.content = COLORS[current()];
    };
    sync();
    button.hidden = false;
    button.addEventListener("click", () => {
      root.dataset.theme = next();
      write(root.dataset.theme);
      sync();
    });
    systemDark.addEventListener("change", sync);
  });
})();
