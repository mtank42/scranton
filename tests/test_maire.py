"""Maire de Scranton: today's mayor and the reminder window."""

from datetime import date

from backend.app.domain.models import TeamMember
from backend.app.services.team_service import TeamService, next_occurrence


def seed_birthdays(session_factory) -> None:
    """A roster around a fixed 'today' of 2026-06-15."""
    with session_factory() as session:
        session.add_all(
            [
                TeamMember(full_name="Kelly", birthday=date(2000, 6, 15)),
                TeamMember(full_name="Darryl", birthday=date(2000, 6, 18)),
                TeamMember(full_name="Stanley", birthday=date(2000, 9, 1)),
                TeamMember(full_name="Ryan"),  # no birthday given: never listed
                TeamMember(full_name="Creed", birthday=date(2000, 6, 16), is_active=False),
            ]
        )
        session.commit()


TODAY = date(2026, 6, 15)


def test_birthday_today_makes_the_mayor(session_factory):
    """Day + month match: Maire de Scranton for 24 hours."""
    seed_birthdays(session_factory)
    overview = TeamService(session_factory).mayor_overview(today=TODAY)
    assert overview.mayor.full_name == "Kelly"


def test_upcoming_lists_the_reminder_window_only(session_factory):
    """J-3 is in, J-78 is out, departed members never appear."""
    seed_birthdays(session_factory)
    overview = TeamService(session_factory).mayor_overview(today=TODAY)
    assert [(u.member.full_name, u.in_days) for u in overview.upcoming] == [("Darryl", 3)]


def test_no_birthday_no_noise(session_factory):
    """An empty roster (or no birthdays) yields a silent overview."""
    overview = TeamService(session_factory).mayor_overview(today=TODAY)
    assert overview.mayor is None
    assert overview.upcoming == []


def test_year_rollover_and_leap_day():
    """Late-December reminders reach into January; Feb 29 lands on Feb 28."""
    assert (next_occurrence(date(2000, 1, 2), date(2026, 12, 30)) - date(2026, 12, 30)).days == 3
    # 2027 is not a leap year: the ritual happens on February 28.
    assert next_occurrence(date(2000, 2, 29), date(2027, 1, 10)) == date(2027, 2, 28)


def test_mayor_endpoint_shape(app, client):
    """The HTTP surface exposes mayor and upcoming."""
    response = client.get("/api/v1/team/mayor")
    assert response.status_code == 200
    assert set(response.json()) == {"mayor", "upcoming"}