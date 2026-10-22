/*
 * Mode clair ou sombre. Par défaut, celui du système ; un clic sur le bouton de l'en-tête
 * impose l'autre, retenu par ce navigateur seulement (stockage local, ni cookie ni
 * serveur). Chargé dans <head>, avant la feuille de style : pas de clignotement.
 */
(function () {
  "use strict";
  const KEY = "theme";
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
  if (saved === "light" || saved === "dark") root.dataset.theme = saved;

  function isDark() {
    return root.dataset.theme ? root.dataset.theme === "dark" : systemDark.matches;
  }

  document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("bouton-theme");
    if (!button) return;
    const sync = () => button.setAttribute("aria-pressed", String(isDark()));
    sync();
    button.hidden = false;
    button.addEventListener("click", () => {
      const next = isDark() ? "light" : "dark";
      root.dataset.theme = next;
      write(next);
      sync();
    });
    systemDark.addEventListener("change", sync);
  });
})();
