/*
 * Formulaire d'événement : signale pendant la saisie, avant l'enregistrement, l'occupation
 * de la salle et les intervenants attendus ailleurs au même moment (CLAUDE.md AGE-7).
 * Le serveur refait le contrôle de toute façon ; les intervenants n'avertissent que.
 */
(function () {
  "use strict";
  const form = document.getElementById("formulaire-evenement");
  if (!form) return;
  const box = document.getElementById("verification-salle");
  const speakersBox = document.getElementById("verification-intervenants");
  const field = (name) => form.querySelector(`[name="${name}"]`);
  let timer = null;

  function item(text) {
    const li = document.createElement("li");
    li.textContent = text;
    return li;
  }

  async function check() {
    const day = field("day").value;
    const start = field("start_time").value;
    const end = field("end_time").value;
    const room = field("room").value;
    const speakers = field("speakers") ? field("speakers").value.trim() : "";
    box.replaceChildren();
    box.className = "room-check";
    speakersBox.replaceChildren();
    speakersBox.className = "room-check";
    if (!day || !start || !end || (!room && !speakers)) return;
    const params = new URLSearchParams({
      start: `${day}T${start.slice(0, 5)}:00`,
      end: `${day}T${end.slice(0, 5)}:00`,
      room,
      speakers,
      exclude: form.dataset.exclude || "",
    });
    const response = await fetch(`${form.dataset.checkUrl}?${params}`, { credentials: "same-origin" });
    if (!response.ok) return;
    const data = await response.json();
    if (data.speakers.length) {
      speakersBox.className = "room-check room-check--warning";
      const ul = document.createElement("ul");
      data.speakers.forEach((w) => ul.appendChild(item(w)));
      speakersBox.append(ul);
    }
    if (!room) return;
    if (data.closed) {
      box.className = "room-check room-check--error";
      box.textContent = data.closed;
    } else if (data.conflicts.length) {
      box.className = "room-check room-check--error";
      const p = document.createElement("p");
      p.textContent = "Salle déjà réservée sur ce créneau : choisissez un autre horaire ou une autre salle.";
      const ul = document.createElement("ul");
      data.conflicts.forEach((c) => ul.appendChild(item(c)));
      box.append(p, ul);
    } else if (data.warnings.length) {
      box.className = "room-check room-check--warning";
      const p = document.createElement("p");
      p.textContent = "La salle est aussi envisagée pour :";
      const ul = document.createElement("ul");
      data.warnings.forEach((w) => ul.appendChild(item(w.replace(/^Même salle que /, ""))));
      box.append(p, ul);
    } else {
      box.className = "room-check room-check--ok";
      box.textContent = data.approval
        ? "Salle libre sur ce créneau. Elle est soumise à validation : la réservation restera en attente jusqu'à l'accord d'un gestionnaire."
        : "Salle libre sur ce créneau.";
    }
  }

  form.addEventListener("change", (event) => {
    if (["day", "start_time", "end_time", "room", "speakers"].includes(event.target.name)) {
      window.clearTimeout(timer);
      timer = window.setTimeout(check, 250);
    }
  });
  check();
})();
