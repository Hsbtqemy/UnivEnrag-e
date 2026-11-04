/*
 * Agenda public : un vrai calendrier, même vide, au-dessus de la liste des prochains
 * événements. À l'ouverture, la semaine en cours si elle a des rendez-vous publics (le
 * serveur le dit : `initialView`), sinon le mois, la forme qu'on reconnaît tout de suite ;
 * on change ensuite librement de vue. Sur téléphone, la semaine est une liste : sept
 * colonnes horaires n'y tiendraient pas. Une période sans rendez-vous le dit dans la
 * grille, sans sauter ailleurs. Lecture seule ; un clic ouvre la fiche.
 */
(function () {
  "use strict";
  const { readConfig, baseOptions } = window.Calendrier;
  const config = readConfig("calendar-config");
  const empty = document.getElementById("agenda-vide");
  const narrow = window.matchMedia("(max-width: 640px)").matches;
  const weekView = narrow ? "listWeek" : "timeGridWeek";
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
    view: config.initialView === "week" ? weekView : "dayGridMonth",
    headerToolbar: {
      start: "prev,next today",
      center: "title",
      end: `dayGridMonth,${weekView}`,
    },
    // Un rendez-vous avant 8 h ou après 21 h élargit la grille de la semaine au lieu
    // d'en sortir.
    flexibleSlotTimeLimits: true,
    eventSources: [{ url: config.eventsUrl }],
    // Un nombre fixe : avec des cases plus hautes, le calcul automatique en cachait.
    dayMaxEvents: 3,
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
  // Sur téléphone, la case d'un jour du mois ne tient que l'heure ; la liste de la
  // semaine, elle, a la place pour le titre.
  if (narrow) {
    options.eventContent = (info) => ({
      domNodes: [
        document.createTextNode(
          info.view.type === "dayGridMonth"
            ? info.timeText
            : `${info.timeText} · ${info.event.title}`
        ),
      ],
    });
  }
  const calendarOptions = baseOptions(options);
  if (narrow) {
    // La liste ne montre ici que la semaine : son bouton le dit.
    const text = calendarOptions.buttonText;
    calendarOptions.buttonText = (t) => ({ ...text(t), listWeek: "Semaine" });
    calendarOptions.views.listWeek.buttonText = calendarOptions.buttonText;
  }
  ec = window.EventCalendar.create(document.getElementById("calendrier"), calendarOptions);
})();
