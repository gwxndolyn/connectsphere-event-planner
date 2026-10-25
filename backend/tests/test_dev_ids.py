"""The dev user ids the frontend and CI's E2E send (dev mode, D12) must be the seeded users' ids, which
`seed_id` derives from fixed slugs. A drift shows up here instead of as 401s in CI (PR #78 review).
No TC ID: it guards configuration, not a story's behaviour."""

import re

import pytest

from app.seed import ATTENDEES, EVENT_COORDINATOR_LEAD_EMAILS, seed_id
from tests.conftest import BACKEND_DIR

REPO = BACKEND_DIR.parent
EXPECTED = {
    "VITE_DEV_USER_ID": seed_id("user", "event-organiser"),
    "VITE_DEV_COORDINATOR_ID": seed_id("user", "event-coordinator"),
    "VITE_DEV_LEAD_ID": seed_id("user", EVENT_COORDINATOR_LEAD_EMAILS[0]),
    "VITE_DEV_VENUE_STAFF_ID": seed_id("user", "venue-staff"),
    "VITE_DEV_TECH_SUPPORT_ID": seed_id("user", "tech-support"),
    # Acting as → Safety officer (SCRUM-121, TC-US16B-22).
    "VITE_DEV_SAFETY_OFFICER_ID": seed_id("user", "safety-officer"),
    "VITE_DEV_ATTENDEE_ID": seed_id("attendee", ATTENDEES[0]),
}


def _values(text: str) -> dict[str, str]:
    # `KEY=value` in .env.example and `KEY: value` in the workflow's env block.
    return dict(re.findall(r"^\s*(VITE_DEV_[A-Z_]+_ID)\s*[=:]\s*(\S+)", text, flags=re.MULTILINE))


@pytest.mark.parametrize("path", ["frontend/.env.example", ".github/workflows/e2e.yml"])
def test_dev_ids_match_the_seeded_users(path: str) -> None:
    found = _values((REPO / path).read_text())

    assert found == {key: str(value) for key, value in EXPECTED.items()}
