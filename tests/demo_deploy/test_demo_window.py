"""Tests for the demo-deploy 14-business-day window — REQ-31.

Covers the pure window model: ``add_business_days`` arithmetic (weekends
skipped, month rollover, negative offsets) and ``DemoWindow`` status
transitions ACTIVE → REMINDER_DUE → EXPIRED with the renewal reminder firing
before expiry.
"""

from __future__ import annotations

from datetime import date

from quantlab.phase4.demo_deploy import (
    DemoWindow,
    DemoWindowStatus,
    add_business_days,
)

# Mon 2026-08-03 → +14 business days = Fri 2026-08-21 (two full weeks).
_START = date(2026, 8, 3)
_EXPIRY = date(2026, 8, 21)
_REMINDER = date(2026, 8, 19)  # 2 business days before expiry (Wed)


class TestAddBusinessDays:
    """Business-day arithmetic: only Mon-Fri count."""

    def test_weekend_skipped_forward(self) -> None:
        """GIVEN a Friday
        WHEN adding one business day
        THEN the result is the following Monday.
        """
        assert add_business_days(date(2026, 8, 7), 1) == date(2026, 8, 10)

    def test_five_business_days_is_one_week(self) -> None:
        """GIVEN a Monday
        WHEN adding five business days
        THEN the result is the following Monday (weekend skipped).
        """
        assert add_business_days(date(2026, 8, 10), 5) == date(2026, 8, 17)

    def test_negative_offset_skips_weekend_backwards(self) -> None:
        """GIVEN a Monday
        WHEN subtracting one business day
        THEN the result is the previous Friday.
        """
        assert add_business_days(date(2026, 8, 10), -1) == date(2026, 8, 7)

    def test_crosses_month_boundary(self) -> None:
        """GIVEN a Friday at month end
        WHEN adding two business days
        THEN the result lands in the next month, skipping the weekend.
        """
        assert add_business_days(date(2026, 8, 28), 2) == date(2026, 9, 1)


class TestDemoWindow:
    """REQ-31: 14-business-day demo window lifecycle."""

    def test_expires_at_is_14_business_days_after_start(self) -> None:
        """GIVEN a demo window started on a Monday
        WHEN computing expiry
        THEN it is exactly 14 business days later (Fri, two full weeks).
        """
        window = DemoWindow(started_at=_START)
        assert window.expires_at == _EXPIRY

    def test_reminder_fires_2_business_days_before_expiry(self) -> None:
        """GIVEN the demo window
        WHEN computing the reminder date
        THEN it is 2 business days before expiry (Wed before the Fri expiry).
        """
        window = DemoWindow(started_at=_START)
        assert window.reminder_at == _REMINDER

    def test_status_active_well_inside_window(self) -> None:
        """GIVEN a campaign two business days into the window
        WHEN checking status
        THEN it is ACTIVE — deploy proceeds without reminder.
        """
        window = DemoWindow(started_at=_START)
        assert window.status(date(2026, 8, 5)) == DemoWindowStatus.ACTIVE

    def test_status_active_the_day_before_reminder(self) -> None:
        """GIVEN the day before the reminder date
        WHEN checking status
        THEN it is still ACTIVE (reminder has not fired yet).
        """
        window = DemoWindow(started_at=_START)
        assert window.status(date(2026, 8, 18)) == DemoWindowStatus.ACTIVE

    def test_status_reminder_due_on_reminder_date(self) -> None:
        """GIVEN the reminder date (2 business days before expiry)
        WHEN checking status
        THEN it is REMINDER_DUE — renewal reminder is scheduled.
        """
        window = DemoWindow(started_at=_START)
        assert window.status(_REMINDER) == DemoWindowStatus.REMINDER_DUE

    def test_status_expired_on_expiry_date(self) -> None:
        """GIVEN the expiry date
        WHEN checking status
        THEN it is EXPIRED — renewal must block pending human approval.
        """
        window = DemoWindow(started_at=_START)
        assert window.status(_EXPIRY) == DemoWindowStatus.EXPIRED

    def test_status_expired_after_expiry(self) -> None:
        """GIVEN a date after expiry
        WHEN checking status
        THEN it is still EXPIRED (deadline is a hard stop).
        """
        window = DemoWindow(started_at=_START)
        assert window.status(date(2026, 8, 25)) == DemoWindowStatus.EXPIRED

    def test_is_expired_and_reminder_due_helpers(self) -> None:
        """GIVEN the window at various dates
        WHEN calling the boolean helpers
        THEN they agree with the status enum.
        """
        window = DemoWindow(started_at=_START)
        assert not window.is_expired(date(2026, 8, 5))
        assert window.is_expired(_EXPIRY)
        assert window.reminder_due(_REMINDER)
        assert not window.reminder_due(date(2026, 8, 18))
