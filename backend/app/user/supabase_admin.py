"""The slice of the Supabase Auth Admin API the seed needs (US16a, SCRUM-104): create a confirmed login,
or find the one the seed created on an earlier run. Admin calls take the project's secret key, so this
runs only from the backend's seed, never from the browser."""

import uuid

import httpx

# How many users one page of the admin list returns while looking an email up, and how many pages to read
# before giving up, so a server that ignores `page` can't loop forever.
PAGE_SIZE = 200
MAX_PAGES = 50

# Stamped on every login the seed creates. An existing account without it was made by someone else (anyone
# can sign up with an unused email), so the seed never links it to a seeded row (PR #56 review).
SEED_MARK = {"seeded_by": "app.seed"}


class SupabaseAdminError(Exception):
    """An Admin API call failed. The message names the email and status, never the key or password."""


class SupabaseAdmin:
    def __init__(self, url: str, secret_key: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self._client = httpx.Client(
            base_url=f"{url.rstrip('/')}/auth/v1/admin",
            # Supabase's own clients send the key in both headers; the gateway accepts either form.
            headers={"apikey": secret_key, "Authorization": f"Bearer {secret_key}"},
            timeout=15,
            transport=transport,
        )

    def __repr__(self) -> str:
        return f"SupabaseAdmin({self._client.base_url})"

    def ensure_user(self, email: str, password: str) -> uuid.UUID:
        """The id of `email`'s login: created already confirmed and marked as the seed's, or the one the
        seed created on an earlier run, reused as it is (its password isn't changed). An existing account
        the seed didn't create, or one that isn't confirmed, is refused."""
        try:
            response = self._client.post(
                "/users",
                json={"email": email, "password": password, "email_confirm": True, "app_metadata": SEED_MARK},
            )
            if response.is_success:
                return uuid.UUID(response.json()["id"])
            if not _already_exists(response):
                raise SupabaseAdminError(
                    f"Supabase Admin API refused {email}: {response.status_code} {_reason(response)}"
                )
            user = self._find_by_email(email)
            if (user.get("app_metadata") or {}).get("seeded_by") != SEED_MARK["seeded_by"]:
                raise SupabaseAdminError(f"{email} already has a Supabase account the seed didn't create")
            if not user.get("email_confirmed_at"):
                raise SupabaseAdminError(f"{email} has a Supabase account that isn't confirmed")
            return uuid.UUID(user["id"])
        # A timeout, a non-JSON body or a missing id names the email like any refusal (TC-US16A-31).
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise SupabaseAdminError(
                f"Supabase Admin API call for {email} failed: {type(error).__name__}"
            ) from None

    def _find_by_email(self, email: str) -> dict:
        for page in range(1, MAX_PAGES + 1):
            response = self._client.get("/users", params={"page": page, "per_page": PAGE_SIZE})
            if not response.is_success:
                raise SupabaseAdminError(
                    f"Supabase Admin API couldn't list users to find {email}: {response.status_code} {_reason(response)}"
                )
            users = response.json().get("users", [])
            for user in users:
                if (user.get("email") or "").lower() == email.lower():
                    return user
            if not users:
                raise SupabaseAdminError(f"Supabase says {email} exists but no user has that email")
        raise SupabaseAdminError(f"Supabase Admin API listed {MAX_PAGES} pages without finding {email}")


def _already_exists(response: httpx.Response) -> bool:
    if response.status_code != 422:
        return False
    body = _json(response)
    return body.get("error_code") in {"email_exists", "user_already_exists"} or "already" in str(
        body.get("msg", "")
    ).lower()


def _reason(response: httpx.Response) -> str:
    body = _json(response)
    return str(body.get("msg") or body.get("message") or body.get("error_code") or "")


def _json(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}
