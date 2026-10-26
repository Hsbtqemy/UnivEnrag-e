from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.template import Context, Template

from apps.core.dates import format_fr, from_wall_clock, to_wall_clock

PARIS = ZoneInfo("Europe/Paris")


def test_round_trip_in_paris_time():
    value = datetime(2026, 11, 10, 14, 30, tzinfo=PARIS)
    assert to_wall_clock(value) == "2026-11-10T14:30:00"
    assert from_wall_clock("2026-11-10T14:30:00") == value


def test_offset_is_ignored_wall_clock_wins():
    assert from_wall_clock("2026-11-10T14:30:00+05:00") == datetime(
        2026, 11, 10, 14, 30, tzinfo=PARIS
    )


def test_date_only_means_midnight():
    assert from_wall_clock("2026-11-10") == datetime(2026, 11, 10, 0, 0, tzinfo=PARIS)


def test_invalid_values_give_none():
    assert from_wall_clock("") is None
    assert from_wall_clock("n'importe quoi") is None
    assert from_wall_clock("2026-13-45T99:00:00") is None


def test_format_fr_writes_first_of_month_as_1er():
    assert format_fr(date(2026, 11, 1), "l j F Y") == "dimanche 1er novembre 2026"
    assert format_fr(date(2026, 11, 2), "j F") == "2 novembre"
    assert format_fr(None, "j F") == ""


def test_date_fr_filter_uses_local_time():
    """Minuit et demie à Paris le 1er novembre, c'est encore le 31 octobre en UTC."""
    moment = datetime(2026, 10, 31, 23, 30, tzinfo=ZoneInfo("UTC"))
    out = Template('{% load dates_fr %}{{ d|date_fr:"j F" }}').render(Context({"d": moment}))
    assert out == "1er novembre"
