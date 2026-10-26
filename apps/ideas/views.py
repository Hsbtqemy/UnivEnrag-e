from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_safe

from apps.accounts.capabilities import has_capability, is_manager, require_capability
from apps.actors.resolvers import remember_name
from apps.actors.services import get_or_create_for_name
from apps.agenda.models import Event
from apps.core import ratelimit
from apps.core.access import public_view

from . import services
from .forms import ProposeForm, PublicReactionForm, PublishForm, RefuseForm, TrackingForm
from .models import Idea, IdeaSlot, Reaction

SPAM_REASON = "Proposition non retenue."


@public_view
def propose(request):
    form = ProposeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        limit, window = settings.PROPOSAL_RATE_LIMIT
        if not ratelimit.hit(request, "propose", limit, window):
            return render(request, "429.html", status=429)
        if form.is_spam():
            # Ignoré en silence : un robot ne doit pas apprendre ce qui l'a trahi.
            return redirect("ideas:sent")
        data = form.cleaned_data
        idea = services.submit(
            kind=data["kind"],
            owner_name=data["owner_name"],
            owner_email=data["owner_email"],
            owner_hidden=data["owner_hidden"],
            title=data["title"],
            description=data["description"],
            duration_minutes=data["duration_minutes"],
            audience=data["audience"],
            expected_count=data["expected_count"],
            wanted_room=data["wanted_room"],
            slots=data["slots"],
        )
        return redirect(reverse("ideas:track", args=[idea.tracking_token]) + "?nouvelle=1")
    return render(request, "ideas/propose.html", {"form": form})


@public_view
def sent(request):
    return render(request, "ideas/sent.html")


@public_view
def track(request, token):
    idea = get_object_or_404(
        Idea.objects.select_related("owner", "wanted_room").prefetch_related("slots"),
        tracking_token=token,
    )
    event = idea.events.exclude(status=Event.Status.CANCELLED).order_by("start").first()
    form = None
    if idea.is_editable_by_owner:
        form = TrackingForm(request.POST or None, instance=Idea.objects.get(pk=idea.pk))
        if request.method == "POST" and form.is_valid():
            services.update_by_owner(idea, **form.cleaned_data)
            messages.success(request, "Vos corrections sont enregistrées.")
            return redirect("ideas:track", token=token)
    return render(
        request,
        "ideas/track.html",
        {
            "idea": idea,
            "event": event,
            "form": form,
            "is_new": request.GET.get("nouvelle") == "1",
            "tracking_url": request.build_absolute_uri(
                reverse("ideas:track", args=[idea.tracking_token])
            ),
        },
    )


# --- Idées sur la page publique ----------------------------------------------------------


def can_publish(user) -> bool:
    """Afficher une idée publiquement : droit « modération » ou « page publique »."""
    return has_capability(user, "moderate") or has_capability(user, "manage_public")


@require_safe
@public_view
def public_list(request):
    ideas = Idea.objects.public().select_related("owner", "space").order_by("-created_at")
    return render(request, "ideas/public_list.html", {"ideas": ideas})


@require_safe
@public_view
def public_detail(request, pk):
    idea = get_object_or_404(Idea.objects.public().select_related("owner", "space"), pk=pk)
    return render(
        request,
        "ideas/public_detail.html",
        {
            "idea": idea,
            "events": Event.objects.public().filter(idea=idea).order_by("start"),
            "reactions": services.reaction_counts(idea),
            "form": PublicReactionForm(actor_name=request.actor_name),
        },
    )


@require_POST
@public_view
def public_react(request, pk):
    idea = get_object_or_404(Idea.objects.public(), pk=pk)
    form = PublicReactionForm(request.POST, actor_name=request.actor_name)
    if not form.is_valid():
        messages.error(request, "Indiquez votre nom pour réagir.")
        return redirect("ideas:public_detail", pk=pk)
    limit, window = settings.PUBLIC_REACTION_RATE_LIMIT
    if not ratelimit.hit(request, "public_reaction", limit, window):
        return render(request, "429.html", status=429)
    name, kind = form.cleaned_data["author_name"], form.cleaned_data["kind"]
    added = services.add_public_reaction(idea, actor=get_or_create_for_name(name), kind=kind)
    label = Reaction.Kind(kind).label
    messages.success(request, f"Merci, « {label} » est noté." if added else "C'était déjà noté.")
    response = redirect(reverse("ideas:public_detail", args=[pk]) + "#reactions")
    remember_name(response, name)
    return response


@require_POST
def publish(request, pk):
    """Afficher ou retirer une idée de la page publique (depuis sa fiche interne)."""
    if not is_manager(request.user):
        return redirect_to_login(request.get_full_path())
    if not can_publish(request.user):
        raise PermissionDenied("Droit « modération » ou « page publique » nécessaire.")
    idea = get_object_or_404(Idea, pk=pk)
    form = PublishForm(request.POST)
    form.is_valid()
    try:
        idea = services.set_public(
            idea,
            user=request.user,
            is_public=form.cleaned_data["is_public"],
            owner_hidden=form.cleaned_data["owner_hidden"],
        )
    except services.TransitionError as error:
        messages.error(request, str(error))
    else:
        messages.success(
            request,
            "Idée affichée sur la page publique."
            if idea.is_public
            else "Idée réservée aux membres.",
        )
    return redirect(reverse("ideas:detail", args=[pk]) + "#page-publique")


# --- Modération ---------------------------------------------------------------------------


@require_capability("moderate")
def moderation(request):
    slots = Prefetch("slots", queryset=IdeaSlot.objects.order_by("rank"))
    base = Idea.objects.select_related("owner", "wanted_room").prefetch_related(slots)
    return render(
        request,
        "gestion/moderation.html",
        {
            "pending": base.filter(status=Idea.Status.PENDING).order_by("created_at"),
            # Seulement ce qui a été modéré : les idées des membres n'y passent pas.
            "recent": base.exclude(status=Idea.Status.PENDING)
            .filter(moderated_at__isnull=False)
            .order_by("-moderated_at")[:20],
            "refuse_form": RefuseForm(),
        },
    )


@require_capability("moderate")
@require_POST
def moderation_accept(request, pk):
    idea = get_object_or_404(Idea, pk=pk)
    try:
        idea = services.accept(idea, user=request.user, public="public" in request.POST)
    except services.TransitionError as error:
        messages.error(request, str(error))
        return redirect("ideas:moderation")
    if idea.events.exists():
        message = f"« {idea.title} » est acceptée et placée en provisoire."
    elif idea.kind == Idea.Kind.EVENT:
        message = f"« {idea.title} » est acceptée : elle attend d'être placée (« À placer »)."
    else:
        message = f"« {idea.title} » est acceptée : elle rejoint les idées."
    if idea.is_public:
        message += " Elle est affichée sur la page publique."
    messages.success(request, message)
    return redirect("ideas:moderation")


@require_capability("moderate")
@require_POST
def moderation_refuse(request, pk):
    idea = get_object_or_404(Idea, pk=pk)
    form = RefuseForm(request.POST)
    reason = form.cleaned_data["reason"] if form.is_valid() else ""
    try:
        services.refuse(idea, user=request.user, reason=reason)
    except services.TransitionError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"« {idea.title} » n'est pas retenue.")
    return redirect("ideas:moderation")


@require_capability("moderate")
@require_POST
def moderation_refuse_bulk(request):
    ids = request.POST.getlist("ids")
    ideas = Idea.objects.filter(pk__in=ids, status=Idea.Status.PENDING)
    count = 0
    for idea in ideas:
        services.refuse(idea, user=request.user, reason=SPAM_REASON)
        count += 1
    if count:
        messages.success(request, f"{count} proposition(s) écartée(s).")
    else:
        messages.info(request, "Aucune proposition sélectionnée.")
    return redirect("ideas:moderation")
