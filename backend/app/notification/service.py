import logging
import uuid
from datetime import date, datetime
from typing import Literal, Protocol

logger = logging.getLogger(__name__)

# Who an assignment notice is for (SCRUM-68). Reassignment (SCRUM-83) adds more.
AssignmentRecipient = Literal["coordinator", "organiser"]


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

    def venue_booking_requested(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
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

    def assignment_made(
        self,
        *,
        email: str,
        recipient: AssignmentRecipient,
        request_reference: str,
        event_name: str,
        coordinator_name: str,
        event_dates: list[date],
    ) -> None: ...

    def equipment_line_reviewed(
        self,
        *,
        email: str,
        line_id: uuid.UUID,
        event_name: str,
        equipment_type: str,
        quantity: int,
        decision: str,
        note: str | None,
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

    def venue_booking_requested(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> None:
        logger.info(
            "venue booking requested: %s, %r at %r from %s to %s (booking %s)",
            email,
            event_name,
            venue_name,
            starts_at,
            ends_at,
            booking_id,
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

    def assignment_made(
        self,
        *,
        email: str,
        recipient: AssignmentRecipient,
        request_reference: str,
        event_name: str,
        coordinator_name: str,
        event_dates: list[date],
    ) -> None:
        # SCRUM-68 AC 1, 2: the coordinator hears they own the event, the organiser who it is.
        logger.info(
            "coordinator assigned (%s notice): %s, %s (%s), coordinator %s, dates %s",
            recipient,
            email,
            request_reference,
            event_name,
            coordinator_name,
            ", ".join(day.isoformat() for day in event_dates),
        )

    def equipment_line_reviewed(
        self,
        *,
        email: str,
        line_id: uuid.UUID,
        event_name: str,
        equipment_type: str,
        quantity: int,
        decision: str,
        note: str | None,
    ) -> None:
        # US26 AC 5: the coordinator who asked hears Tech Support's decision on the line.
        logger.info(
            "equipment line %s: %s, %d x %s for %r (line %s), note: %s",
            decision,
            email,
            quantity,
            equipment_type,
            event_name,
            line_id,
            note or "none",
        )


notifier = LoggingNotifier()


def get_notifier() -> Notifier:
    return notifier
