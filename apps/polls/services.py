from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from .models import Poll, PollAnswer, PollSlot

MIN_SLOTS, MAX_SLOTS = 2, 8


class PollError(Exception):
    pass


@transaction.atomic
def create(*, actor, title, slots, description="", space=None, room=None) -> Poll:
    """`slots` : suite de (début, fin)."""
    slots = sorted(set(slots))
    if not MIN_SLOTS <= len(slots) <= MAX_SLOTS:
        raise PollError(f"Proposez entre {MIN_SLOTS} et {MAX_SLOTS} créneaux différents.")
    now = timezone.now()
    for start, end in slots:
        if end <= start:
            raise PollError("Chaque créneau doit finir après avoir commencé.")
        if start <= now:
            raise PollError("Les créneaux proposés doivent être à venir.")
    poll = Poll.objects.create(
        owner=actor, title=title, description=description, space=space, room=room
    )
    PollSlot.objects.bulk_create(PollSlot(poll=poll, start=s, end=e) for s, e in slots)
    return poll


@transaction.atomic
def answer(poll: Poll, *, actor, answers: dict) -> None:
    """Remplace les réponses de `actor` : {id du créneau: "yes" | "maybe" | ""}."""
    if poll.is_closed:
        raise PollError("Ce sondage est clos.")
    slots = {s.pk: s for s in poll.slots.all()}
    PollAnswer.objects.filter(slot__poll=poll, actor=actor).delete()
    PollAnswer.objects.bulk_create(
        PollAnswer(slot=slots[slot_id], actor=actor, answer=value)
        for slot_id, value in answers.items()
        if slot_id in slots and value in PollAnswer.Answer.values
    )


def close_with_event(poll: Poll, event) -> Poll:
    poll.event = event
    poll.is_closed = True
    poll.save(update_fields=["event", "is_closed"])
    return poll


@dataclass
class SlotResult:
    slot: PollSlot
    yes: int = 0
    maybe: int = 0
    is_best: bool = False

    @property
    def score(self) -> tuple[int, int]:
        return (self.yes, self.maybe)


@dataclass
class Results:
    slots: list
    rows: list = field(default_factory=list)  # (nom, [réponse par créneau])
    participants: int = 0


def results(poll: Poll) -> Results:
    slots = list(poll.slots.all())
    answers = PollAnswer.objects.filter(slot__poll=poll).select_related("actor")
    by_actor: dict = {}
    per_slot = {s.pk: SlotResult(s) for s in slots}
    for a in answers:
        by_actor.setdefault(a.actor.display_name, {})[a.slot_id] = a.answer
        if a.answer == PollAnswer.Answer.YES:
            per_slot[a.slot_id].yes += 1
        else:
            per_slot[a.slot_id].maybe += 1
    ordered = [per_slot[s.pk] for s in slots]
    best = max((r.score for r in ordered), default=(0, 0))
    if best > (0, 0):
        for r in ordered:
            r.is_best = r.score == best
    rows = [
        (name, [answers_.get(s.pk, "") for s in slots])
        for name, answers_ in sorted(by_actor.items(), key=lambda item: item[0].casefold())
    ]
    return Results(slots=ordered, rows=rows, participants=len(rows))


def answers_of(poll: Poll, actor) -> dict:
    if actor is None:
        return {}
    return dict(
        PollAnswer.objects.filter(slot__poll=poll, actor=actor).values_list("slot_id", "answer")
    )
