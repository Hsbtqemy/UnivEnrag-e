"""Idées des membres (CDC §4) : derrière le code d'accès, sous le nom de chacun."""

from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.capabilities import has_capability, is_manager
from apps.actors.resolvers import remember_name
from apps.actors.services import get_or_create_for_name
from apps.agenda.models import Event
from apps.agenda.services import EventError

from . import services
from .forms import IdeaFilterForm, IdeaForm, ReactionForm, StatusForm
from .models import Idea, IdeaSlot, Reaction

# Tri du tableau : clé dans l'adresse → ordre en base. Le premier est celui par défaut.
SORTS = {
    "date": ("-created_at",),
    "interet": ("-interest", "-created_at"),
    "titre": ("title",),
}


def _get_idea(request, pk) -> Idea:
    """Une idée visible ; les propositions à modérer ne se voient qu'en modération."""
    idea = get_object_or_404(
        Idea.objects.select_related("owner", "space", "wanted_room", "updated_by"), pk=pk
    )
    if idea.status not in Idea.VISIBLE_STATUSES and not has_capability(request.user, "moderate"):
        raise Http404("Idée introuvable.")
    return idea


def _done(response, name):
    remember_name(response, name)  # CLAUDE.md ACC-2
    return response


def idea_list(request):
    """Tableau triable par intérêt et par date, filtrable par type, espace, public, statut."""
    ideas = Idea.objects.visible()
    audiences = sorted(set(ideas.exclude(audience="").values_list("audience", flat=True)))
    filters = IdeaFilterForm(request.GET or None, audiences=audiences)
    sort = request.GET.get("tri", "date")
    if sort not in SORTS:
        sort = "date"
    ideas = (
        filters.filter(ideas)
        .select_related("owner", "space")
        .annotate(
            interest=Count("reactions__actor", distinct=True),
            participants=Count(
                "reactions", filter=Q(reactions__kind=Reaction.Kind.PARTICIPATE), distinct=True
            ),
        )
        .order_by(*SORTS[sort])
    )
    query = request.GET.copy()
    query.pop("tri", None)
    return render(
        request,
        "ideas/list.html",
        {
            "ideas": ideas,
            "filters": filters,
            "sort": sort,
            "query": query.urlencode(),
            "to_place": Idea.objects.to_place().count(),
        },
    )


def idea_new(request):
    form = IdeaForm(request.POST or None, actor_name=request.actor_name)
    if request.method == "POST" and form.is_valid():
        actor = get_or_create_for_name(form.cleaned_data["author_name"])
        kwargs = form.service_kwargs()
        idea = services.create(
            actor=actor, title=kwargs.pop("title"), kind=kwargs.pop("kind"), **kwargs
        )
        if idea.events.exists():
            messages.success(
                request,
                f"« {idea.title} » est déposée et placée en provisoire sur votre créneau préféré.",
            )
        else:
            messages.success(request, f"« {idea.title} » est déposée.")
        return _done(redirect("ideas:detail", pk=idea.pk), form.cleaned_data["author_name"])
    return render(request, "ideas/form.html", {"form": form, "idea": None})


def idea_detail(request, pk):
    idea = _get_idea(request, pk)
    mine = set()
    if request.actor is not None:
        mine = set(idea.reactions.filter(actor=request.actor).values_list("kind", flat=True))
    reactions = services.reactions_by_kind(idea)
    for reaction in reactions:
        reaction["mine"] = reaction["kind"] in mine
    return render(
        request,
        "ideas/detail.html",
        {
            "idea": idea,
            "slots": IdeaSlot.objects.filter(idea=idea),
            "events": idea.events.select_related("room").order_by("start"),
            "reactions": reactions,
            "reaction_form": ReactionForm(actor_name=request.actor_name),
            "status_form": StatusForm(
                initial={"status": idea.status}, actor_name=request.actor_name
            )
            if idea.status in Idea.MANUAL_STATUSES
            else None,
            # L'e-mail d'un porteur extérieur reste réservé à la gestion (CLAUDE.md PUB-2).
            "show_email": is_manager(request.user) and bool(idea.owner_email),
            "can_create_event": idea.status in Idea.VISIBLE_STATUSES
            and idea.status != Idea.Status.ABANDONED,
        },
    )


def idea_edit(request, pk):
    idea = _get_idea(request, pk)
    if not idea.is_editable:
        messages.error(request, "Cette idée ne peut pas être modifiée.")
        return redirect("ideas:detail", pk=pk)
    form = IdeaForm(request.POST or None, instance=idea, actor_name=request.actor_name)
    if request.method == "POST" and form.is_valid():
        services.update(
            idea,
            actor=get_or_create_for_name(form.cleaned_data["author_name"]),
            **form.service_kwargs(),
        )
        messages.success(request, "Idée mise à jour.")
        return _done(redirect("ideas:detail", pk=pk), form.cleaned_data["author_name"])
    return render(request, "ideas/form.html", {"form": form, "idea": idea})


@require_POST
def idea_react(request, pk):
    idea = _get_idea(request, pk)
    form = ReactionForm(request.POST, actor_name=request.actor_name)
    if not form.is_valid():
        messages.error(request, "Indiquez votre nom pour réagir.")
        return redirect("ideas:detail", pk=pk)
    kind = form.cleaned_data["kind"]
    try:
        added = services.toggle_reaction(
            idea, actor=get_or_create_for_name(form.cleaned_data["author_name"]), kind=kind
        )
    except services.TransitionError as error:
        messages.error(request, str(error))
        return redirect("ideas:detail", pk=pk)
    label = Reaction.Kind(kind).label
    messages.success(request, f"« {label} » ajouté." if added else f"« {label} » retiré.")
    response = redirect(reverse("ideas:detail", args=[pk]) + "#reactions")
    return _done(response, form.cleaned_data["author_name"])


@require_POST
def idea_status(request, pk):
    idea = _get_idea(request, pk)
    form = StatusForm(request.POST, actor_name=request.actor_name)
    if not form.is_valid():
        messages.error(request, "Indiquez votre nom et le nouveau statut.")
        return redirect("ideas:detail", pk=pk)
    provisional = idea.events.filter(status=Event.Status.PROVISIONAL).count()
    try:
        idea = services.set_status(
            idea,
            form.cleaned_data["status"],
            actor=get_or_create_for_name(form.cleaned_data["author_name"]),
        )
    except services.TransitionError as error:
        messages.error(request, str(error))
        return redirect("ideas:detail", pk=pk)
    except EventError as error:  # un placement à annuler est verrouillé
        messages.error(request, f"Statut inchangé : {error}")
        return redirect("ideas:detail", pk=pk)
    message = f"Statut : {idea.get_status_display()}."
    if idea.status == Idea.Status.ABANDONED and provisional:
        message += " Ses placements provisoires sont annulés."
    messages.success(request, message)
    return _done(redirect("ideas:detail", pk=pk), form.cleaned_data["author_name"])
