/*
 * Agenda des membres : clic sur un créneau → formulaire de création pré-rempli ;
 * glisser-déposer → déplacement immédiat, sous le nom retenu par le navigateur.
 * Le serveur reste seul juge (verrou, conflit de salle, version périmée).
 */
(function () {
  "use strict";
  const { wallClock, readConfig, postJSON, baseOptions } = window.Calendrier;
  const config = readConfig("calendar-config");
  const announcer = document.getElementById("annonce");
  const filter = document.getElementById("filtre-salle");

  function announce(message, isError) {
    announcer.textContent = message;
    announcer.classList.toggle("live--error", Boolean(isError));
  }

  function openNew(start, end) {
    const params = new URLSearchParams({ debut: wallClock(start) });
    if (end) params.set("fin", wallClock(end));
    if (filter.value && filter.value !== "aucune") params.set("salle", filter.value);
    window.location.href = `${config.newUrl}?${params}`;
  }

  async function move(info) {
    if (!config.canEdit) {
      info.revert();
      announce("Indiquez d'abord votre nom (en haut de la page) pour modifier l'agenda.", true);
      return;
    }
    const result = await postJSON(config.moveUrl.replace("/0/", `/${info.event.id}/`), {
      start: wallClock(info.event.start),
      end: wallClock(info.event.end),
      revision: info.event.extendedProps.revision,
    });
    if (!result.ok) {
      info.revert();
      announce(result.error, true);
    } else {
      let message = `« ${info.event.title} » déplacé.`;
      if (result.warnings.length) {
        const inline = result.warnings.map((w) => w.charAt(0).toLowerCase() + w.slice(1));
        message += ` Attention : ${inline.join(" ; ")}.`;
      }
      announce(message);
    }
    ec.refetchEvents();
  }

  const narrow = window.matchMedia("(max-width: 640px)").matches;
  const options = {
    // Vue liste par défaut sur téléphone (CDC §3).
    view: narrow ? "listWeek" : "timeGridWeek",
    headerToolbar: { start: "prev,next today", center: "title", end: "dayGridMonth,timeGridWeek,listWeek" },
    eventSources: [{ url: config.eventsUrl }],
    selectable: true,
    pointer: true,
    dayMaxEvents: true,
    snapDuration: "00:15:00",
    noEventsContent: "Aucun événement sur cette période.",
    eventFilter(info) {
      const wanted = filter.value;
      if (!wanted) return true;
      const roomId = info.event.extendedProps.roomId;
      return wanted === "aucune" ? !roomId : String(roomId) === wanted;
    },
    eventContent(info) {
      const props = info.event.extendedProps;
      const title = document.createElement("span");
      title.className = "ev-title";
      title.textContent = info.event.title;
      const meta = document.createElement("span");
      meta.className = "ev-meta";
      meta.textContent = props.status === "confirmed" ? props.place : `${props.statusLabel} · ${props.place}`;
      return { domNodes: [title, meta] };
    },
    eventClick(info) {
      window.location.href = info.event.extendedProps.url;
    },
    dateClick(info) {
      openNew(info.date, null);
    },
    select(info) {
      openNew(info.start, info.end);
    },
    eventDrop: move,
    eventResize: move,
  };
  if (config.date) options.date = config.date;

  const ec = window.EventCalendar.create(document.getElementById("calendrier"), baseOptions(options));

  filter.addEventListener("change", () => {
    // Réappliquer le filtre : on redonne la même fonction pour forcer le rendu.
    ec.setOption("eventFilter", options.eventFilter);
  });
})();
