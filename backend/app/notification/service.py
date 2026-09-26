import logging
from datetime import datetime
from typing import Protocol

logger = logging.getLogger(__name__)


class Notifier(Protocol):
    """What the domain needs to tell people things. Tests assert on the calls (TC-US7-08)."""

    def waitlist_offer(self, *, email: str, event_name: str, expires_at: datetime) -> None: ...


class LoggingNotifier:
    """Sprint 1 stand-in: no mail is sent, the call is logged (spec §7)."""

    def waitlist_offer(self, *, email: str, event_name: str, expires_at: datetime) -> None:
        logger.info(
            "waitlist offer: %s may claim a seat for %r until %s", email, event_name, expires_at
        )


notifier = LoggingNotifier()


def get_notifier() -> Notifier:
    return notifier
