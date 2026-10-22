from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.actors.resolvers import remember_name
from apps.actors.services import get_or_create_for_name

from . import services
from .forms import AnswerForm, PollForm
from .models import Poll


def poll_list(request):
    polls = Poll.objects.select_related("owner", "event").prefetch_related("slots")
    return render(
        request,
        "polls/list.html",
        {
            "open_polls": polls.filter(is_closed=False),
            "closed_polls": polls.filter(is_closed=True)[:10],
        },
    )


def poll_new(request):
    form = PollForm(request.POST or None, actor_name=request.actor_name)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            poll = services.create(
                actor=get_or_create_for_name(data["author_name"]),
                title=data["title"],
                description=data["description"],
                space=data["space"],
                room=data["room"],
                slots=data["slots"],
            )
        except services.PollError as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, "Sondage créé. Partagez son adresse pour que chacun réponde.")
            response = redirect("polls:detail", pk=poll.pk)
            remember_name(response, data["author_name"])
            return response
    return render(request, "polls/new.html", {"form": form})


def poll_detail(request, pk):
    poll = get_object_or_404(Poll.objects.select_related("owner", "event", "room", "space"), pk=pk)
    slots = list(poll.slots.all())
    form = AnswerForm(
        request.POST or None,
        slots=slots,
        current=services.answers_of(poll, request.actor),
        actor_name=request.actor_name,
    )
    if request.method == "POST" and form.is_valid():
        try:
            services.answer(
                poll,
                actor=get_or_create_for_name(form.cleaned_data["author_name"]),
                answers=form.answers(),
            )
        except services.PollError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Vos réponses sont enregistrées.")
        response = redirect("polls:detail", pk=pk)
        remember_name(response, form.cleaned_data["author_name"])
        return response
    return render(
        request,
        "polls/detail.html",
        {"poll": poll, "results": services.results(poll), "form": form},
    )
