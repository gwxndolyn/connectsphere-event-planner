import logging
import uuid
from datetime import date, datetime
from typing import Protocol

logger = logging.getLogger(__name__)


class Notifier(Protocol):
    """What the domain needs to tell people things. Tests assert on the calls (TC-US7-08)."""

    def waitlist_offer(
        self, *, email: str, event_name: str, expires_at: datetime, registration_id: uuid.UUID
    ) -> None: ...

    def clarification_requested(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        round: int,
        sections: list[str],
        comment: str,
    ) -> None: ...

    def request_queued(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        organiser_name: str,
        preferred_dates: list[date],
    ) -> None: ...


class LoggingNotifier:
    """Sprint 1 stand-in: no mail is sent, the call is logged (spec §7)."""

    def waitlist_offer(
        self, *, email: str, event_name: str, expires_at: datetime, registration_id: uuid.UUID
    ) -> None:
        # registration_id is what the attendee accepts with: POST /registrations/{id}/accept.
        logger.info(
            "waitlist offer: %s may claim a seat for %r until %s (registration %s)",
            email,
            event_name,
            expires_at,
            registration_id,
        )

    def clarification_requested(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        round: int,
        sections: list[str],
        comment: str,
    ) -> None:
        logger.info(
            "clarification requested: %s, %s (%s, round %d), sections %s: %s",
            email,
            request_reference,
            event_name,
            round,
            ", ".join(sections),
            comment,
        )

    def request_queued(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        organiser_name: str,
        preferred_dates: list[date],
    ) -> None:
        # SCRUM-13 AC 11: tells a Coordinator Lead a new request is waiting in the unassigned queue.
        logger.info(
            "request queued: %s, %s (%s) from %s, preferred dates %s",
            email,
            request_reference,
            event_name,
            organiser_name,
            ", ".join(day.isoformat() for day in preferred_dates),
        )


notifier = LoggingNotifier()


def get_notifier() -> Notifier:
    return notifier
