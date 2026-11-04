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
# What the Safety Officer decided on an event's arrangements (SCRUM-99).
SafetyOutcome = Literal["approved", "rejected"]
# What a hold notice says (US25, SCRUM-93, AC 4): one was placed, it expires within 24 hours, or it expired.
HoldStage = Literal["placed", "expiring", "expired"]
# Who a cancellation notice is for (US9, SCRUM-12, AC 6).
CancellationRecipient = Literal["organiser", "venue_staff", "tech_support", "attendee"]
# Who hears a venue became unavailable under their event's booking (US23a, SCRUM-90, AC 4). Never attendees.
UnavailabilityRecipient = Literal["coordinator", "organiser"]
# What Venue staff decided on a coordinator's request to restore a booking (US23b, SCRUM-91, AC 5).
RestoreDecision = Literal["confirmed", "declined"]


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

    def event_confirmed(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        starts_at: datetime,
        ends_at: datetime,
        venues: list[str],
    ) -> None: ...

    def safety_review_decided(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        outcome: SafetyOutcome,
        comments: str | None,
        issues: list[str],
    ) -> None: ...

    def safety_changes_requested(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        comments: str,
        areas: list[str],
        issues: list[str],
    ) -> None: ...


    def change_requested(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        organiser_name: str,
        fields: list[str],
        reason: str,
        to_lead: bool,
    ) -> None: ...

    def change_request_decided(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        decision: str,
        fields: list[str],
        rejection_reason: str | None,
        status_change: str | None,
        safety_review_required: bool,
        to_requester: bool,
    ) -> None: ...

    def arrangement_flagged(
        self, *, email: str, event_id: uuid.UUID, event_name: str, kind: str, label: str, fields: list[str]
    ) -> None: ...

    def cancellation_requested(
        self, *, email: str, event_id: uuid.UUID, event_name: str, organiser_name: str, reason: str
    ) -> None: ...

    def venue_held(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
        expires_at: datetime,
        stage: HoldStage,
    ) -> None: ...

    def venue_unavailable(
        self,
        *,
        email: str,
        recipient: UnavailabilityRecipient,
        event_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
        reason: str,
        booking_references: list[str],
        next_action: str,
    ) -> None: ...

    def venue_restore_requested(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        booking_reference: str,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> None: ...

    def venue_restore_decided(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        booking_reference: str,
        event_name: str,
        venue_name: str,
        decision: RestoreDecision,
        reason: str | None,
    ) -> None: ...

    def venue_changed(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> None: ...

    def venue_period_ended(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        booking_reference: str,
        event_name: str,
        venue_name: str,
        ended_at: datetime,
    ) -> None: ...

    def venue_booking_needs_review(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        reference: str,
        starts_at: datetime,
        ends_at: datetime,
        reason: str,
    ) -> None: ...

    def cancellation_rejected(
        self, *, email: str, event_id: uuid.UUID, event_name: str, reason: str, rejection_reason: str
    ) -> None: ...

    def event_cancelled(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        reason: str,
        recipient: CancellationRecipient,
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

    def event_confirmed(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        starts_at: datetime,
        ends_at: datetime,
        venues: list[str],
    ) -> None:
        # SCRUM-85 AC 4: the organiser hears the event is confirmed, with its date, time and venue(s).
        logger.info(
            "event confirmed: %s, %s (%s) from %s to %s at %s",
            email,
            request_reference,
            event_name,
            starts_at.isoformat(),
            ends_at.isoformat(),
            ", ".join(venues),
        )

    def safety_review_decided(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        outcome: SafetyOutcome,
        comments: str | None,
        issues: list[str],
    ) -> None:
        # SCRUM-99 AC 5: the event's coordinator hears the outcome, the comments and what was flagged.
        logger.info(
            "safety review %s: %s, %s (%s); issues: %s; comments: %s",
            outcome,
            email,
            request_reference,
            event_name,
            ", ".join(issues) or "none",
            comments or "none",
        )

    def safety_changes_requested(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        comments: str,
        areas: list[str],
        issues: list[str],
    ) -> None:
        # SCRUM-100 (US30b) AC 3: the event's coordinator hears the comments and the areas to review.
        logger.info(
            "safety changes requested: %s, %s (%s); areas: %s; issues: %s; comments: %s",
            email,
            request_reference,
            event_name,
            ", ".join(areas),
            ", ".join(issues) or "none",
            comments,
        )


    def change_requested(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        organiser_name: str,
        fields: list[str],
        reason: str,
        to_lead: bool,
    ) -> None:
        # US29a (SCRUM-97) AC 5: the event's coordinator hears an organiser asked for a change; a Lead when
        # nobody is assigned yet (D91).
        logger.info(
            "change requested: %s%s, %r (%s) by %s, fields %s; reason: %s",
            email,
            " (Lead, unassigned)" if to_lead else "",
            event_name,
            event_id,
            organiser_name,
            ", ".join(fields),
            reason,
        )


    def change_request_decided(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        decision: str,
        fields: list[str],
        rejection_reason: str | None,
        status_change: str | None,
        safety_review_required: bool,
        to_requester: bool,
    ) -> None:
        # US29b (SCRUM-142) AC 4: the requester hears the decision, and the organiser too when an approved US12
        # edit changed their event (D102).
        logger.info(
            "change request %s: %s%s, %r (%s), fields %s%s%s%s",
            decision,
            email,
            "" if to_requester else " (organiser)",
            event_name,
            event_id,
            fields,
            f"; reason: {rejection_reason}" if rejection_reason else "",
            f"; back to {status_change}" if status_change else "",
            "; a new safety review is needed" if safety_review_required else "",
        )

    def arrangement_flagged(
        self, *, email: str, event_id: uuid.UUID, event_name: str, kind: str, label: str, fields: list[str]
    ) -> None:
        # US29b (SCRUM-142) D104: Venue staff and Tech support hear an approved change may have overtaken what
        # they arranged. Nothing on it changed.
        logger.info("arrangement flagged for review: %s, %s %s on %r (%s), changed %s", email, kind, label, event_name, event_id, fields)

    def cancellation_requested(
        self, *, email: str, event_id: uuid.UUID, event_name: str, organiser_name: str, reason: str
    ) -> None:
        # US9 (SCRUM-12) AC 2: the event's coordinator hears the organiser asked to cancel it.
        logger.info("cancellation requested: %s, %r (%s) by %s; reason: %s", email, event_name, event_id,
                    organiser_name, reason)

    def cancellation_rejected(
        self, *, email: str, event_id: uuid.UUID, event_name: str, reason: str, rejection_reason: str
    ) -> None:
        # US9 AC 2: the organiser hears their request was rejected, and why; the event goes ahead.
        logger.info("cancellation rejected: %s, %r (%s); asked: %s; rejected: %s", email, event_name, event_id,
                    reason, rejection_reason)

    def event_cancelled(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        reason: str,
        recipient: CancellationRecipient,
    ) -> None:
        # US9 AC 2, 6: everyone involved hears the event is cancelled, with its name and the reason.
        logger.info("event cancelled: %s (%s), %r (%s); reason: %s", email, recipient, event_name, event_id, reason)


    def venue_held(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
        expires_at: datetime,
        stage: HoldStage,
    ) -> None:
        # US25 (SCRUM-93) AC 1, 4: the event's coordinator hears a venue is held, that the hold expires within
        # 24 hours (D103), and that it expired.
        logger.info(
            "venue hold %s: %s, %s for %r %s to %s, expires %s (booking %s)",
            stage,
            email,
            venue_name,
            event_name,
            starts_at.isoformat(),
            ends_at.isoformat(),
            expires_at.isoformat(),
            booking_id,
        )

    def venue_unavailable(
        self,
        *,
        email: str,
        recipient: UnavailabilityRecipient,
        event_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
        reason: str,
        booking_references: list[str],
        next_action: str,
    ) -> None:
        # US23a (SCRUM-90) AC 4: the coordinator and the organiser of an event whose booking or hold the period
        # overlaps hear the venue, the period, the reason and what happens next.
        logger.info(
            "venue unavailable (%s): %s, %s %s to %s (%s) under %r (%s) bookings %s; next: %s",
            recipient,
            email,
            venue_name,
            starts_at.isoformat(),
            ends_at.isoformat(),
            reason,
            event_name,
            event_id,
            ", ".join(booking_references),
            next_action,
        )

    def venue_restore_requested(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        booking_reference: str,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> None:
        # US23b (SCRUM-91) AC 5: every active Venue staff member hears a coordinator asked to restore a booking.
        logger.info(
            "venue restore requested: %s, %s at %s %s to %s for %r (%s)",
            email,
            booking_reference,
            venue_name,
            starts_at.isoformat(),
            ends_at.isoformat(),
            event_name,
            booking_id,
        )

    def venue_restore_decided(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        booking_reference: str,
        event_name: str,
        venue_name: str,
        decision: RestoreDecision,
        reason: str | None,
    ) -> None:
        # US23b AC 5: the coordinator who asked, and the event's coordinator, hear Venue staff's decision.
        logger.info(
            "venue restore %s: %s, %s at %s for %r (%s)%s",
            decision,
            email,
            booking_reference,
            venue_name,
            event_name,
            booking_id,
            f"; reason: {reason}" if reason else "",
        )

    def venue_changed(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> None:
        # US23b AC 7: an attendee hears only once a replacement is approved and the venue or times they see changed.
        logger.info(
            "venue changed: %s, %r (%s) now at %s, %s to %s",
            email,
            event_name,
            event_id,
            venue_name,
            starts_at.isoformat(),
            ends_at.isoformat(),
        )

    def venue_period_ended(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        booking_reference: str,
        event_name: str,
        venue_name: str,
        ended_at: datetime,
    ) -> None:
        # US23b AC 5 (Matt's #134 review): the coordinator hears a period that marked their booking ended early, so
        # they know they can ask to restore it.
        logger.info(
            "venue period ended early: %s, %s at %s for %r (%s) ended %s",
            email,
            booking_reference,
            venue_name,
            event_name,
            booking_id,
            ended_at.isoformat(),
        )

    def venue_booking_needs_review(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        reference: str,
        starts_at: datetime,
        ends_at: datetime,
        reason: str,
    ) -> None:
        # US20 AC 2 (SCRUM-147): Venue staff and the event's coordinator hear that a capacity or hours edit left a live
        # future booking needing review. Nothing about the booking changed (D119).
        logger.info(
            "venue booking needs review: %s, %s at %s %s to %s for %r (%s): %s",
            email,
            reference,
            venue_name,
            starts_at.isoformat(),
            ends_at.isoformat(),
            event_name,
            event_id,
            reason,
        )


notifier = LoggingNotifier()


def get_notifier() -> Notifier:
    # US31 (SCRUM-107): the logging notifier plus a row for each recipient. Imported here because the
    # recorder reads the other stories' models, and those modules import this one for the Notifier type.
    from app.notification.recorder import recording_notifier

    return recording_notifier
