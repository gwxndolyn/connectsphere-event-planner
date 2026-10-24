"""US16a, PR 4 (SCRUM-104): the seed creates a Supabase Auth login for every seeded user and links it.
The Admin API is faked (or served by httpx.MockTransport), so nothing reaches the network."""

import json
import uuid
from contextlib import nullcontext

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.seed as seed_module
from app.core.config import settings
from app.seed import SEEDED_LOGIN_EMAILS, SeedAuthError, seed, seed_auth_logins
from app.user.models import User
from app.user.supabase_admin import SEED_MARK, SupabaseAdmin, SupabaseAdminError
from tests.factories import NOW

PASSWORD = "seed-dev-password-123"
SECRET = "sb_secret_test_value_never_printed"
SUPABASE_URL = "https://test-project.supabase.co"


class FakeAdmin:
    """Stands in for SupabaseAdmin. `accounts` is the fake Supabase Auth user list, by email."""

    def __init__(self, fail_for: str | None = None) -> None:
        self.accounts: dict[str, uuid.UUID] = {}
        self.created: list[dict[str, object]] = []
        self.fail_for = fail_for

    def ensure_user(self, email: str, password: str) -> uuid.UUID:
        if email == self.fail_for:
            raise SupabaseAdminError(f"Supabase Admin API refused {email}: 500")
        if email not in self.accounts:
            self.accounts[email] = uuid.uuid4()
            self.created.append({"email": email, "password": password, "email_confirm": True})
        return self.accounts[email]


def seeded_users(db: Session) -> dict[str, User]:
    users = db.scalars(select(User).where(User.email.in_(SEEDED_LOGIN_EMAILS)))
    return {user.email: user for user in users}


def test_tc_us16a_27_every_seeded_user_gets_a_confirmed_linked_login(db: Session) -> None:
    seed(db, now=NOW)
    admin = FakeAdmin()

    seed_auth_logins(db, admin, PASSWORD)

    assert len(SEEDED_LOGIN_EMAILS) == 10
    assert {account["email"] for account in admin.created} == set(SEEDED_LOGIN_EMAILS)
    assert all(account["password"] == PASSWORD and account["email_confirm"] for account in admin.created)
    users = seeded_users(db)
    assert {email: user.auth_user_id for email, user in users.items()} == admin.accounts


def test_tc_us16a_28_a_row_linked_to_another_account_is_not_repointed(db: Session) -> None:
    # E.g. a real person signed up with a demo attendee's address and #55 linked it (PR #56 review).
    seed(db, now=NOW)
    taken = seeded_users(db)[SEEDED_LOGIN_EMAILS[-1]]
    their_account = uuid.uuid4()
    taken.auth_user_id = their_account
    db.commit()

    with pytest.raises(SeedAuthError, match=taken.email):
        seed_auth_logins(db, FakeAdmin(), PASSWORD)

    users = seeded_users(db)
    assert users[taken.email].auth_user_id == their_account
    assert all(user.auth_user_id is None for email, user in users.items() if email != taken.email)


def test_tc_us16a_28_reseeding_reuses_existing_logins(db: Session) -> None:
    seed(db, now=NOW)
    admin = FakeAdmin()
    seed_auth_logins(db, admin, PASSWORD)
    links_before = {email: user.auth_user_id for email, user in seeded_users(db).items()}

    seed(db, now=NOW)
    seed_auth_logins(db, admin, PASSWORD)

    assert len(admin.created) == len(SEEDED_LOGIN_EMAILS)
    assert {email: user.auth_user_id for email, user in seeded_users(db).items()} == links_before


@pytest.mark.parametrize(
    ("url", "secret", "admin", "password", "missing"),
    [
        (SUPABASE_URL, "", None, PASSWORD, "SUPABASE_SECRET_KEY not set"),
        ("", SECRET, None, PASSWORD, "SUPABASE_URL not set"),
        (SUPABASE_URL, SECRET, FakeAdmin(), None, "SEED_AUTH_PASSWORD not set"),
    ],
    ids=["no secret key", "no url", "no password"],
)
def test_tc_us16a_29_without_credentials_logins_are_skipped(
    db: Session,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    secret: str,
    admin,
    password,
    missing: str,
) -> None:
    monkeypatch.setattr(settings, "supabase_url", url)
    monkeypatch.setattr(settings, "supabase_secret_key", SecretStr(secret))
    seed(db, now=NOW)

    seed_auth_logins(db, admin, password)

    output = capsys.readouterr().out
    assert "skipped" in output and missing in output
    users = seeded_users(db)
    assert len(users) == len(SEEDED_LOGIN_EMAILS)
    assert all(user.auth_user_id is None for user in users.values())


def test_tc_us16a_29_a_short_password_is_refused_and_links_nothing(db: Session) -> None:
    # One shared password protects staff logins too (PR #56 review).
    seed(db, now=NOW)
    admin = FakeAdmin()

    with pytest.raises(SeedAuthError, match="at least 12 characters"):
        seed_auth_logins(db, admin, "short-pass1")

    assert admin.created == []
    assert all(user.auth_user_id is None for user in seeded_users(db).values())


def test_tc_us16a_30_the_password_never_appears_in_the_output(
    db: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    seed(db, now=NOW)

    seed_auth_logins(db, FakeAdmin(), PASSWORD)

    output = capsys.readouterr().out
    assert PASSWORD not in output
    assert all(email in output for email in SEEDED_LOGIN_EMAILS)


def test_tc_us16a_31_an_admin_api_failure_names_the_email_and_links_nothing(db: Session) -> None:
    seed(db, now=NOW)
    failing = SEEDED_LOGIN_EMAILS[2]

    with pytest.raises(SeedAuthError, match=failing):
        seed_auth_logins(db, FakeAdmin(fail_for=failing), PASSWORD)

    assert all(user.auth_user_id is None for user in seeded_users(db).values())


def test_tc_us16a_31_main_returns_1_when_a_login_fails(
    db: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    failing = SEEDED_LOGIN_EMAILS[0]
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://u:p@localhost:5432/test")
    monkeypatch.setattr(settings, "seed_auth_password", SecretStr(PASSWORD))
    monkeypatch.setattr(seed_module, "SessionLocal", lambda: nullcontext(db))
    monkeypatch.setattr(seed_module, "admin_from_settings", lambda: FakeAdmin(fail_for=failing))

    assert seed_module.main() == 1
    assert failing in capsys.readouterr().out


# The real client, against a fake Supabase served by httpx.MockTransport.


def admin_with(handler) -> SupabaseAdmin:
    return SupabaseAdmin(SUPABASE_URL, SECRET, transport=httpx.MockTransport(handler))


def test_tc_us16a_27_the_client_creates_a_confirmed_user_with_the_secret_key() -> None:
    created_id = uuid.uuid4()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": str(created_id), "email": "a@smu.edu.sg"})

    assert admin_with(handler).ensure_user("a@smu.edu.sg", PASSWORD) == created_id
    request = requests[0]
    assert (request.method, str(request.url)) == ("POST", f"{SUPABASE_URL}/auth/v1/admin/users")
    assert json.loads(request.content) == {
        "email": "a@smu.edu.sg",
        "password": PASSWORD,
        "email_confirm": True,
        "app_metadata": SEED_MARK,
    }
    assert request.headers["apikey"] == SECRET
    assert request.headers["Authorization"] == f"Bearer {SECRET}"


CONFIRMED = "2026-10-24T03:00:00Z"


def existing_account_handler(account: dict | None, *, pages: int = 2):
    """A fake Supabase where `a@smu.edu.sg` already exists: creating it is refused, and listing finds
    `account` on page 2 (or nobody, when it's None)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(422, json={"code": 422, "error_code": "email_exists", "msg": "already registered"})
        page = int(request.url.params.get("page", "1"))
        users = [{"id": str(uuid.uuid4()), "email": "other@smu.edu.sg"}]
        if page == 2 and account is not None:
            users = [account]
        if page > pages:
            users = []
        return httpx.Response(200, json={"users": users})

    return handler


def test_tc_us16a_28_the_client_reuses_an_account_that_already_exists() -> None:
    existing_id = uuid.uuid4()
    account = {"id": str(existing_id), "email": "A@smu.edu.sg", "app_metadata": SEED_MARK, "email_confirmed_at": CONFIRMED}

    assert admin_with(existing_account_handler(account)).ensure_user("a@smu.edu.sg", PASSWORD) == existing_id


@pytest.mark.parametrize(
    ("account", "reason"),
    [
        ({"app_metadata": {}, "email_confirmed_at": CONFIRMED}, "the seed didn't create"),
        ({"app_metadata": {"provider": "email"}, "email_confirmed_at": CONFIRMED}, "the seed didn't create"),
        ({"app_metadata": SEED_MARK, "email_confirmed_at": None}, "isn't confirmed"),
    ],
    ids=["no mark", "someone else's sign-up", "unconfirmed"],
)
def test_tc_us16a_28_the_client_refuses_an_account_the_seed_did_not_create(account: dict, reason: str) -> None:
    # Anyone can sign up with an unused staff email first; that account must never be linked (PR #56 review).
    account = {"id": str(uuid.uuid4()), "email": "a@smu.edu.sg", **account}

    with pytest.raises(SupabaseAdminError, match=reason):
        admin_with(existing_account_handler(account)).ensure_user("a@smu.edu.sg", PASSWORD)


def test_tc_us16a_31_exists_but_no_listed_user_has_the_email() -> None:
    with pytest.raises(SupabaseAdminError, match="exists but no user has that email"):
        admin_with(existing_account_handler(None)).ensure_user("a@smu.edu.sg", PASSWORD)


def test_tc_us16a_31_listing_stops_after_a_page_cap() -> None:
    # A server that ignores `page` keeps returning the same non-empty page.
    with pytest.raises(SupabaseAdminError, match="without finding"):
        admin_with(existing_account_handler(None, pages=10_000)).ensure_user("a@smu.edu.sg", PASSWORD)


def raise_timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectTimeout("timed out", request=request)


@pytest.mark.parametrize(
    "handler",
    [
        raise_timeout,
        lambda request: httpx.Response(200, text="<html>not json</html>"),
        lambda request: httpx.Response(200, json={"email": "a@smu.edu.sg"}),
    ],
    ids=["timeout", "non-JSON body", "no id"],
)
def test_tc_us16a_31_any_client_failure_names_the_email(handler) -> None:
    with pytest.raises(SupabaseAdminError, match="a@smu.edu.sg") as raised:
        admin_with(handler).ensure_user("a@smu.edu.sg", PASSWORD)

    assert SECRET not in str(raised.value) and PASSWORD not in str(raised.value)


def test_tc_us16a_30_client_errors_never_include_the_secret_or_password() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"msg": "internal error"})

    with pytest.raises(SupabaseAdminError) as raised:
        admin_with(handler).ensure_user("a@smu.edu.sg", PASSWORD)

    message = str(raised.value)
    assert "a@smu.edu.sg" in message and "500" in message
    assert SECRET not in message and PASSWORD not in message
    assert SECRET not in repr(admin_with(handler))
