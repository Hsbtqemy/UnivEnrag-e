/* Agenda public, vue semaine : lecture seule, un clic ouvre la fiche de l'événement. */
(function () {
  "use strict";
  const { readConfig, baseOptions } = window.Calendrier;
  const config = readConfig("calendar-config");
  const element = document.getElementById("calendrier");

  const narrow = window.matchMedia("(max-width: 640px)").matches;

  window.EventCalendar.create(element, baseOptions({
    // Vue liste par défaut sur téléphone (CDC §3).
    view: narrow ? "listWeek" : "timeGridWeek",
    headerToolbar: { start: "prev,next today", center: "title", end: "timeGridWeek,listWeek" },
    eventSources: [{ url: config.eventsUrl }],
    eventClick(info) {
      const url = info.event.extendedProps.url;
      if (url) window.location.href = url;
    },
    pointer: true,
  }));
})();
