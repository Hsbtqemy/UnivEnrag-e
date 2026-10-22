/* Bouton « Imprimer » de la vue imprimable (la CSP interdit les gestionnaires en ligne). */
(function () {
  "use strict";
  const button = document.getElementById("imprimer");
  if (!button) return;
  button.hidden = false;
  button.addEventListener("click", () => window.print());
})();
