/*
 * Formulaire public « Proposer une idée » : la durée, les créneaux et la salle ne
 * concernent qu'un événement. Sans JavaScript, tout reste affiché, et le serveur ignore
 * ces champs pour un projet ou une envie.
 */
(function () {
  "use strict";
  const block = document.getElementById("si-evenement");
  const radios = document.querySelectorAll('input[name="kind"]');
  if (!block || !radios.length) return;

  function update() {
    const checked = document.querySelector('input[name="kind"]:checked');
    block.hidden = checked !== null && checked.value !== "event";
  }

  radios.forEach((radio) => radio.addEventListener("change", update));
  update();
})();
