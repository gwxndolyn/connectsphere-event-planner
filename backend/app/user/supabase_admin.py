"""The slice of the Supabase Auth Admin API the seed needs (US16a, SCRUM-104): create a confirmed login,
or find the one that already exists. Admin calls take the project's secret key, so this runs only from
the backend's seed, never from the browser."""

import uuid

import httpx

# How many users one page of the admin list returns while looking an email up.
PAGE_SIZE = 200


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
        """The id of `email`'s login: created already confirmed, or the existing one, which is
        reused as it is (its password isn't changed)."""
        response = self._client.post("/users", json={"email": email, "password": password, "email_confirm": True})
        if response.is_success:
            return uuid.UUID(response.json()["id"])
        if _already_exists(response):
            return self._find_by_email(email)
        raise SupabaseAdminError(f"Supabase Admin API refused {email}: {response.status_code} {_reason(response)}")

    def _find_by_email(self, email: str) -> uuid.UUID:
        page = 1
        while True:
            response = self._client.get("/users", params={"page": page, "per_page": PAGE_SIZE})
            if not response.is_success:
                raise SupabaseAdminError(
                    f"Supabase Admin API couldn't list users to find {email}: {response.status_code} {_reason(response)}"
                )
            users = response.json().get("users", [])
            for user in users:
                if (user.get("email") or "").lower() == email.lower():
                    return uuid.UUID(user["id"])
            if not users:
                raise SupabaseAdminError(f"Supabase says {email} exists but no user has that email")
            page += 1


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
