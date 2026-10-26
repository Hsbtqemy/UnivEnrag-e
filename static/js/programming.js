/*
 * Vue de programmation (CDC §3) : colonnes par salle, provisoires hachurés, autres
 * créneaux en pointillé, panneau « À placer », filtres. Tout participant place et
 * déplace sous son nom ; confirmer et publier n'apparaissent qu'aux habilités.
 *
 * Toute règle (conflit de salle, version périmée) est vérifiée par le serveur ; ce
 * script ne fait qu'envoyer l'intention et recharger l'affichage.
 */
(function () {
  "use strict";
  const { wallClock, readConfig, postJSON, baseOptions, formatRange, pad } = window.Calendrier;
  const config = readConfig("calendar-config");
  const $ = (id) => document.getElementById(id);
  const urlFor = (template, id) => template.replace("/0/", `/${id}/`);

  const announcer = $("annonce");
  const selection = new Set();
  let pendingIdea = null; // bouton « À placer » choisi, en attente d'un créneau
  let detailsId = null;
  let reopenDetails = false; // rouvrir le panneau quand les événements rechargés sont affichés

  function announce(message, isError) {
    announcer.textContent = message;
    announcer.classList.toggle("live--error", Boolean(isError));
  }

  // --- Calendrier -------------------------------------------------------------------

  // Par défaut, une journée avec une colonne par salle : la semaine par salle multiplie
  // les colonnes (jours × salles) et ne se lit que sur un très grand écran.
  const filters = {
    kind: $("filtre-type"),
    space: $("filtre-espace"),
    audience: $("filtre-public"),
    status: $("filtre-statut"),
  };

  function matches(props) {
    const kind = filters.kind.value;
    if (kind && (kind === "aucun" ? props.ideaKind : props.ideaKind !== kind)) return false;
    const space = filters.space.value;
    if (space && (space === "aucun" ? props.spaceId : String(props.spaceId) !== space)) return false;
    if (filters.audience && filters.audience.value && props.audience !== filters.audience.value) return false;
    if (filters.status.value && props.status !== filters.status.value) return false;
    return true;
  }

  const options = {
    view: "resourceTimeGridDay",
    headerToolbar: {
      start: "prev,next today",
      center: "title",
      end: "resourceTimeGridDay,resourceTimeGridWeek,timeGridWeek",
    },
    resources: config.resources,
    datesAboveResources: true,
    eventSources: [{ url: config.eventsUrl }],
    editable: config.canEdit,
    selectable: config.canEdit,
    pointer: true,
    snapDuration: "00:15:00",
    eventFilter(info) {
      return matches(info.event.extendedProps);
    },
    eventClassNames(info) {
      return selection.has(info.event.id) ? ["is-selected"] : [];
    },
    eventContent(info) {
      const props = info.event.extendedProps;
      const nodes = [];
      const time = document.createElement("span");
      time.className = "ev-time";
      time.textContent = `${pad(info.event.start.getHours())}:${pad(info.event.start.getMinutes())}`;
      nodes.push(time);
      const title = document.createElement("span");
      title.className = "ev-title";
      title.textContent = info.event.title;
      nodes.push(title);
      if (props.kind === "event") {
        const meta = document.createElement("span");
        meta.className = "ev-meta";
        meta.textContent = `${props.statusLabel} · ${props.owner}`;
        nodes.push(meta);
      }
      return { domNodes: nodes };
    },
    eventDrop(info) {
      const room = info.newResource ? info.newResource.id : undefined;
      move(info.event, info.event.start, info.event.end, room, info.revert);
    },
    eventResize(info) {
      move(info.event, info.event.start, info.event.end, undefined, info.revert);
    },
    eventClick(info) {
      const props = info.event.extendedProps;
      if (props.kind === "alternative") {
        moveToAlternative(props);
      } else {
        openDetails(info.event.id);
      }
    },
    dateClick(info) {
      if (!pendingIdea) return;
      place(info.date, null, info.resource ? info.resource.id : null);
    },
    eventAllUpdated() {
      if (reopenDetails && detailsId) openDetails(detailsId);
      reopenDetails = false;
    },
    select(info) {
      if (!pendingIdea) {
        ec.unselect();
        return;
      }
      place(info.start, info.end, info.resource ? info.resource.id : null);
      ec.unselect();
    },
  };
  const ec = window.EventCalendar.create($("calendrier"), baseOptions(options));

  // La bibliothèque ne refiltre que si l'option change : il faut une nouvelle fonction.
  const refilter = () => ec.setOption("eventFilter", (info) => options.eventFilter(info));
  Object.values(filters).forEach((select) => select && select.addEventListener("change", refilter));

  // Avertissements désactivables (CDC §3) : ils ne bloquent jamais rien.
  const warningsToggle = $("voir-avertissements");
  warningsToggle.addEventListener("change", () => {
    document.body.classList.toggle("hide-warnings", !warningsToggle.checked);
  });
  const showWarnings = () => warningsToggle.checked;

  function refresh(withDetails) {
    reopenDetails = Boolean(withDetails && detailsId);
    ec.refetchEvents();
  }

  // --- Déplacement --------------------------------------------------------------------

  async function move(event, start, end, room, revert) {
    const payload = {
      start: wallClock(start),
      end: wallClock(end),
      revision: event.extendedProps.revision,
    };
    if (room !== undefined) payload.room = room;
    const result = await postJSON(urlFor(config.moveUrl, event.id), payload);
    if (!result.ok) {
      if (revert) revert();
      announce(result.error, true);
    } else {
      announce(movedMessage(event.title, result.warnings));
    }
    refresh(detailsId === event.id);
  }

  function withWarnings(message, warnings) {
    if (!warnings || !warnings.length || !showWarnings()) return message;
    const inline = warnings.map((w) => w.charAt(0).toLowerCase() + w.slice(1));
    return `${message} Attention : ${inline.join(" ; ")}.`;
  }

  function movedMessage(title, warnings) {
    return withWarnings(`« ${title} » déplacé.`, warnings);
  }

  function needName() {
    if (config.canEdit) return false;
    announce("Indiquez d'abord votre nom (en haut de la page) pour placer ou déplacer.", true);
    return true;
  }

  // L'événement d'origine peut être hors de la période affichée : le créneau en
  // pointillé porte lui-même sa version et son titre.
  async function moveToAlternative(props) {
    if (needName()) return;
    const result = await postJSON(urlFor(config.moveUrl, props.eventId), {
      start: props.start,
      end: props.end,
      revision: props.revision,
    });
    announce(result.ok ? movedMessage(props.eventTitle, result.warnings) : result.error, !result.ok);
    refresh();
  }

  // --- Panneau « À placer » ----------------------------------------------------------

  const list = $("a-placer-liste");

  function choose(button) {
    const already = pendingIdea === button;
    list.querySelectorAll(".to-place__item").forEach((b) => b.setAttribute("aria-pressed", "false"));
    pendingIdea = already ? null : button;
    if (pendingIdea) {
      pendingIdea.setAttribute("aria-pressed", "true");
      announce(`« ${button.dataset.title} » choisie : cliquez sur un créneau du calendrier. Échap pour annuler.`);
    } else {
      announce("Placement annulé.");
    }
    document.body.classList.toggle("is-placing", Boolean(pendingIdea));
  }

  list.addEventListener("click", (e) => {
    // Sans droit d'écriture, les idées à placer sont de simples fiches, pas des boutons.
    const button = e.target.closest("button.to-place__item");
    if (button) choose(button);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && pendingIdea) choose(pendingIdea);
  });

  async function place(start, end, resourceId) {
    const button = pendingIdea;
    if (needName()) return;
    let room = resourceId;
    if (room === null) room = button.dataset.room || config.freePlaceResource;
    const payload = { start: wallClock(start), room };
    if (end) payload.end = wallClock(end);
    const result = await postJSON(urlFor(config.placeUrl, button.dataset.ideaId), payload);
    if (!result.ok) {
      announce(result.error, true);
      return;
    }
    const item = button.closest("li");
    choose(button);
    item.remove();
    const remaining = list.querySelectorAll(".to-place__item").length;
    $("a-placer-compte").textContent = remaining;
    if (!remaining) {
      const empty = document.createElement("li");
      empty.className = "empty";
      empty.textContent = "Rien à placer.";
      list.appendChild(empty);
    }
    announce(withWarnings(`« ${button.dataset.title} » placée en provisoire.`, result.warnings));
    refresh();
  }

  // --- Sélection et confirmation -----------------------------------------------------

  const confirmButton = $("confirmer-selection");

  function updateSelectionBar() {
    if (!confirmButton) return;
    const n = selection.size;
    $("selection-compte").textContent =
      n === 0 ? "Aucun événement sélectionné" : `${n} événement${n > 1 ? "s" : ""} sélectionné${n > 1 ? "s" : ""}`;
    confirmButton.disabled = n === 0;
  }

  function toggleSelected(id, selected) {
    if (selected) selection.add(id);
    else selection.delete(id);
    updateSelectionBar();
    refresh();
  }

  async function confirmIds(ids) {
    const result = await postJSON(config.confirmUrl, { ids });
    if (result.status >= 400 && !result.confirmed) {
      announce(result.error, true);
      return;
    }
    result.confirmed.forEach((id) => selection.delete(String(id)));
    updateSelectionBar();
    const parts = [];
    if (result.confirmed.length) parts.push(`${result.confirmed.length} confirmé(s).`);
    result.refused.forEach((r) => parts.push(`« ${r.title} » non confirmé : ${r.error}`));
    announce(parts.join(" "), result.refused.length > 0);
    refresh(true);
  }

  if (confirmButton) confirmButton.addEventListener("click", () => confirmIds([...selection]));

  // --- Panneau de détails ------------------------------------------------------------

  const panel = $("details");

  function openDetails(id) {
    const event = ec.getEventById(String(id));
    if (!event) {
      closeDetails();
      return;
    }
    const props = event.extendedProps;
    detailsId = String(id);
    $("details-titre").textContent = event.title;
    $("details-statut").textContent = props.statusLabel + (props.isPublic ? " · public" : " · non public");
    $("details-quand").textContent = formatRange(event.start, event.end);
    $("details-ou").textContent = props.place;
    const owner = $("details-porteur");
    owner.textContent = props.owner;
    if (props.ownerEmail) {
      // Seuls les comptes de gestion reçoivent l'e-mail (CLAUDE.md PUB-2).
      const mail = document.createElement("a");
      mail.href = `mailto:${props.ownerEmail}`;
      mail.textContent = props.ownerEmail;
      owner.append(" · ", mail);
    }

    const warnings = $("details-avertissements");
    warnings.replaceChildren(...(showWarnings() ? props.warnings : []).map((w) => {
      const li = document.createElement("li");
      li.textContent = w;
      return li;
    }));

    if (config.confirmUrl) {
      $("details-selection").checked = selection.has(detailsId);
      $("details-selection").disabled = props.status === "confirmed";
      $("details-confirmer").disabled = props.status === "confirmed";
    }
    if (config.publicUrl) $("details-public").checked = props.isPublic;
    $("details-fiche").href = props.url;
    $("details-idee-lien").hidden = !props.ideaUrl;
    $("details-idee").href = props.ideaUrl || "#";
    // Verrouillé, ou pas de nom : pas de formulaire de déplacement.
    $("details-deplacer").hidden = !config.canEdit || event.editable === false;

    const start = event.start;
    $("deplacer-date").value = `${start.getFullYear()}-${pad(start.getMonth() + 1)}-${pad(start.getDate())}`;
    $("deplacer-debut").value = `${pad(start.getHours())}:${pad(start.getMinutes())}`;
    $("deplacer-fin").value = `${pad(event.end.getHours())}:${pad(event.end.getMinutes())}`;
    $("deplacer-salle").value = props.roomId ? String(props.roomId) : config.freePlaceResource;

    panel.hidden = false;
  }

  function closeDetails() {
    panel.hidden = true;
    detailsId = null;
  }

  $("details-fermer").addEventListener("click", closeDetails);

  if (config.confirmUrl) {
    $("details-selection").addEventListener("change", (e) => {
      if (detailsId) toggleSelected(detailsId, e.target.checked);
    });
    $("details-confirmer").addEventListener("click", () => {
      if (detailsId) confirmIds([detailsId]);
    });
  }

  if (config.publicUrl) $("details-public").addEventListener("change", async (e) => {
    if (!detailsId) return;
    const result = await postJSON(urlFor(config.publicUrl, detailsId), { isPublic: e.target.checked });
    announce(result.ok
      ? (result.isPublic ? "Visible sur l'agenda public une fois confirmé." : "Retiré de l'agenda public.")
      : result.error, !result.ok);
    refresh(true);
  });

  $("details-deplacer").addEventListener("submit", (e) => {
    e.preventDefault();
    const event = detailsId && ec.getEventById(detailsId);
    if (!event) return;
    const day = $("deplacer-date").value;
    const start = new Date(`${day}T${$("deplacer-debut").value}:00`);
    const end = new Date(`${day}T${$("deplacer-fin").value}:00`);
    move(event, start, end, $("deplacer-salle").value, null);
  });

  updateSelectionBar();
})();
