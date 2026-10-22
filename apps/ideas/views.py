from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core import ratelimit

from . import services
from .forms import ProposeForm, RefuseForm, TrackingForm
from .models import Idea, IdeaSlot

SPAM_REASON = "Proposition non retenue."


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
            owner_name=data["owner_name"],
            owner_email=data["owner_email"],
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


def sent(request):
    return render(request, "ideas/sent.html")


def track(request, token):
    idea = get_object_or_404(
        Idea.objects.select_related("owner", "wanted_room").prefetch_related("slots"),
        tracking_token=token,
    )
    event = getattr(idea, "event", None)
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


@staff_member_required
def moderation(request):
    slots = Prefetch("slots", queryset=IdeaSlot.objects.order_by("rank"))
    base = Idea.objects.select_related("owner", "wanted_room").prefetch_related(slots)
    return render(
        request,
        "gestion/moderation.html",
        {
            "pending": base.filter(status=Idea.Status.PENDING).order_by("created_at"),
            "recent": base.exclude(status=Idea.Status.PENDING).order_by("-moderated_at")[:20],
            "refuse_form": RefuseForm(),
        },
    )


@staff_member_required
@require_POST
def moderation_accept(request, pk):
    idea = get_object_or_404(Idea, pk=pk)
    try:
        idea = services.accept(idea, user=request.user)
    except services.TransitionError as error:
        messages.error(request, str(error))
        return redirect("ideas:moderation")
    if hasattr(idea, "event"):
        messages.success(request, f"« {idea.title} » est acceptée et placée en provisoire.")
    else:
        messages.success(request, f"« {idea.title} » est acceptée : elle attend d'être placée.")
    return redirect("ideas:moderation")


@staff_member_required
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


@staff_member_required
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
