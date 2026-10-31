import logging
import uuid
from datetime import date, datetime
from typing import Literal, Protocol

logger = logging.getLogger(__name__)

# Who an assignment notice is for (SCRUM-68).
AssignmentRecipient = Literal["coordinator", "organiser"]
# Who a reassignment notice is for (SCRUM-83 and SCRUM-68's last AC).
ReassignmentRecipient = Literal["new_coordinator", "previous_coordinator", "organiser"]
# What Venue Staff decided on a booking request (SCRUM-8).
BookingDecision = Literal["approved", "rejected"]
# What the coordinator decided on an event request (SCRUM-84).
RequestDecision = Literal["approved", "rejected"]


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

    def venue_booking_decided(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        decision: BookingDecision,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
        reason: str | None,
        alternative_suggestion: str | None,
    ) -> None: ...

    def venue_booking_withdrawn(
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

    def event_reassigned(
        self,
        *,
        email: str,
        recipient: ReassignmentRecipient,
        request_reference: str,
        event_name: str,
        previous_coordinator_name: str,
        new_coordinator_name: str,
        event_dates: list[date],
        reason: str,
    ) -> None: ...

    def transfer_requested(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        coordinator_name: str,
        reason: str,
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

    def request_decided(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        decision: RequestDecision,
        reason: str | None,
    ) -> None: ...

    def tech_staff_assigned(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        starts_at: datetime,
        ends_at: datetime,
        venue_name: str | None,
        location: str | None,
        equipment: list[str],
        equipment_needs: str | None,
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

    def venue_booking_decided(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        decision: BookingDecision,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
        reason: str | None,
        alternative_suggestion: str | None,
    ) -> None:
        # SCRUM-8 AC 6: the coordinator hears whether the venue is theirs; a rejection says why if given.
        logger.info(
            "venue booking %s: %s, %r at %r from %s to %s (booking %s); reason: %s; alternative: %s",
            decision,
            email,
            event_name,
            venue_name,
            starts_at,
            ends_at,
            booking_id,
            reason or "none given",
            alternative_suggestion or "none given",
        )

    def venue_booking_withdrawn(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> None:
        # US24 (SCRUM-128, D69): Venue Staff hear that a venue they approved is free again.
        logger.info(
            "approved venue booking withdrawn: %s, %r at %r from %s to %s (booking %s)",
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

    def event_reassigned(
        self,
        *,
        email: str,
        recipient: ReassignmentRecipient,
        request_reference: str,
        event_name: str,
        previous_coordinator_name: str,
        new_coordinator_name: str,
        event_dates: list[date],
        reason: str,
    ) -> None:
        # SCRUM-83 and SCRUM-68's last AC: the organiser and both coordinators hear the event moved.
        logger.info(
            "event reassigned (%s notice): %s, %s (%s), from %s to %s, dates %s; reason: %s",
            recipient,
            email,
            request_reference,
            event_name,
            previous_coordinator_name,
            new_coordinator_name,
            ", ".join(day.isoformat() for day in event_dates),
            reason,
        )

    def transfer_requested(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        coordinator_name: str,
        reason: str,
    ) -> None:
        # SCRUM-83 AC 6: a Lead hears a coordinator wants an event moved.
        logger.info(
            "transfer requested: %s, %s (%s) by coordinator %s; reason: %s",
            email,
            request_reference,
            event_name,
            coordinator_name,
            reason,
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

    def request_decided(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        decision: RequestDecision,
        reason: str | None,
    ) -> None:
        # SCRUM-84 AC 4: the organiser hears the outcome, and why on a rejection.
        logger.info(
            "event request %s: %s, %s (%s); reason: %s",
            decision,
            email,
            request_reference,
            event_name,
            reason or "none",
        )

    def tech_staff_assigned(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        starts_at: datetime,
        ends_at: datetime,
        venue_name: str | None,
        location: str | None,
        equipment: list[str],
        equipment_needs: str | None,
    ) -> None:
        # US14 AC 4: the staff member hears the event, where it is and what it needs (D82).
        logger.info(
            "tech support assigned: %s to %r (%s) %s to %s at %s, %s; equipment: %s; needs: %s",
            email,
            event_name,
            event_id,
            starts_at.isoformat(),
            ends_at.isoformat(),
            venue_name or "no venue",
            location or "no location",
            ", ".join(equipment) or "none",
            equipment_needs or "none",
        )


notifier = LoggingNotifier()


def get_notifier() -> Notifier:
    return notifier
