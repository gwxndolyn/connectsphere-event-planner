import logging
import uuid
from datetime import datetime
from typing import Protocol

logger = logging.getLogger(__name__)


class Notifier(Protocol):
    """What the domain needs to tell people things. Tests assert on the calls (TC-US7-08)."""

    def waitlist_offer(
        self, *, email: str, event_name: str, expires_at: datetime, registration_id: uuid.UUID
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


notifier = LoggingNotifier()


def get_notifier() -> Notifier:
    return notifier
