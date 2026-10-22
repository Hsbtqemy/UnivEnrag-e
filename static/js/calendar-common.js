/*
 * Outils partagés par les calendriers (@event-calendar, servi en local).
 *
 * Les dates s'échangent en heure murale « AAAA-MM-JJTHH:MM:SS » sans fuseau : c'est
 * l'heure affichée à l'écran qui fait foi, et le serveur l'interprète en heure de Paris.
 */
(function () {
  "use strict";

  const pad = (n) => String(n).padStart(2, "0");

  function wallClock(date) {
    return (
      `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
      `T${pad(date.getHours())}:${pad(date.getMinutes())}:00`
    );
  }

  function readConfig(id) {
    return JSON.parse(document.getElementById(id).textContent);
  }

  function csrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  async function postJSON(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify(payload),
    });
    let data = {};
    try {
      data = await response.json();
    } catch (e) {
      data = { ok: false, error: "Réponse inattendue du serveur." };
    }
    data.status = response.status;
    if (!response.ok && data.ok === undefined) data.ok = false;
    return data;
  }

  const frenchText = (text) => ({
    ...text,
    close: "Fermer",
    today: "Aujourd'hui",
    prev: "Précédent",
    next: "Suivant",
    dayGridMonth: "Mois",
    timeGridWeek: "Semaine",
    timeGridDay: "Jour",
    listWeek: "Liste",
    resourceTimeGridWeek: "Salles · semaine",
    resourceTimeGridDay: "Salles · jour",
  });

  /* Options communes : semaine du lundi, journée de 8 h à 21 h, textes en français. */
  function baseOptions(extra) {
    const views = {};
    ["dayGridMonth", "timeGridWeek", "timeGridDay", "listWeek",
     "resourceTimeGridWeek", "resourceTimeGridDay"].forEach((v) => {
      views[v] = { buttonText: frenchText };
    });
    return {
      locale: "fr-FR",
      firstDay: 1,
      allDaySlot: false,
      slotMinTime: "08:00:00",
      slotMaxTime: "21:00:00",
      scrollTime: "09:00:00",
      slotDuration: "00:30:00",
      nowIndicator: true,
      height: "auto",
      buttonText: frenchText,
      views,
      eventTimeFormat: { hour: "2-digit", minute: "2-digit" },
      slotLabelFormat: { hour: "2-digit", minute: "2-digit" },
      dayHeaderFormat: { weekday: "short", day: "numeric", month: "numeric" },
      ...extra,
    };
  }

  function formatRange(start, end) {
    const day = start.toLocaleDateString("fr-FR", {
      weekday: "long", day: "numeric", month: "long", year: "numeric",
    });
    const time = (d) => d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    return `${day.charAt(0).toUpperCase()}${day.slice(1)}, ${time(start)} – ${time(end)}`;
  }

  window.Calendrier = { wallClock, readConfig, postJSON, baseOptions, formatRange, pad };
})();
