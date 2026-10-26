/*
 * Agenda public : un vrai calendrier, même vide, au-dessus de la liste des prochains
 * événements. Le mois par défaut, sur grand écran comme sur téléphone : c'est la forme
 * qu'on reconnaît tout de suite. Une période sans rendez-vous le dit dans la grille, sans
 * sauter ailleurs. Lecture seule ; un clic ouvre la fiche.
 */
(function () {
  "use strict";
  const { readConfig, baseOptions } = window.Calendrier;
  const config = readConfig("calendar-config");
  const empty = document.getElementById("agenda-vide");
  const narrow = window.matchMedia("(max-width: 640px)").matches;
  let loadingNow = false;
  let ec = null; // créé plus bas ; les rappels peuvent arriver pendant sa création

  // On regarde toute la grille affichée (jours du mois voisin compris) : un rendez-vous
  // visible dans la grille ne doit pas cohabiter avec « aucun rendez-vous ».
  function showEmptyIfNeeded() {
    if (!ec) return;
    const view = ec.getView();
    const hasEvents = ec.getEvents().some(
      (e) => e.start < view.activeEnd && e.end > view.activeStart
    );
    const dayMonth = (d) => {
      const month = d.toLocaleDateString("fr-FR", { month: "long" });
      return `${d.getDate() === 1 ? "1er" : d.getDate()} ${month}`;
    };
    const lastDay = new Date(view.currentEnd.getTime() - 1);
    const period = view.type === "dayGridMonth"
      ? `en ${view.currentStart.toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}`
      : `du ${dayMonth(view.currentStart)} au ${dayMonth(lastDay)}`;
    empty.textContent = `Aucun rendez-vous public ${period} pour l'instant.`;
    empty.hidden = hasEvents;
  }

  const options = {
    view: "dayGridMonth",
    headerToolbar: {
      start: "prev,next today",
      center: "title",
      end: narrow ? "" : "dayGridMonth,timeGridWeek",
    },
    eventSources: [{ url: config.eventsUrl }],
    dayMaxEvents: true,
    displayEventEnd: false,
    eventClick(info) {
      const url = info.event.extendedProps.url;
      if (url) window.location.href = url;
    },
    loading(isLoading) {
      loadingNow = isLoading;
      if (isLoading) empty.hidden = true;
      else setTimeout(showEmptyIfNeeded, 0);
    },
    // Passer du mois à la semaine ne recharge rien : les événements sont déjà là.
    datesSet() {
      empty.hidden = true;
      setTimeout(() => {
        if (!loadingNow) showEmptyIfNeeded();
      }, 50);
    },
    pointer: true,
  };
  // Sur téléphone, la case d'un jour ne tient que l'heure ; le titre est dans la liste.
  if (narrow) {
    options.eventContent = (info) => ({ domNodes: [document.createTextNode(info.timeText)] });
  }
  ec = window.EventCalendar.create(document.getElementById("calendrier"), baseOptions(options));
})();
