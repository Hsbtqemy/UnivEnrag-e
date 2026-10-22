/*
 * Agenda public : la semaine en calendrier au-dessus de la liste des prochains événements.
 * Lecture seule ; un clic ouvre la fiche. Sur téléphone, la grille n'est pas créée : la
 * liste de la page donne les mêmes informations, plus lisibles (CDC §3).
 */
(function () {
  "use strict";
  if (window.matchMedia("(max-width: 640px)").matches) return;
  const { readConfig, baseOptions } = window.Calendrier;
  const config = readConfig("calendar-config");

  window.EventCalendar.create(document.getElementById("calendrier"), baseOptions({
    view: "timeGridWeek",
    headerToolbar: { start: "prev,next today", center: "title", end: "" },
    eventSources: [{ url: config.eventsUrl }],
    eventClick(info) {
      const url = info.event.extendedProps.url;
      if (url) window.location.href = url;
    },
    pointer: true,
  }));
})();
