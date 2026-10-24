import uuid

from pydantic import BaseModel, ConfigDict

from app.user.models import UserRole


class ProfileWrite(BaseModel):
    """Body of POST /api/v1/auth/profile. Both fields are optional here so the service can list every
    missing one (`MISSING_REQUIRED_FIELD`) and tell a staff role apart (`INVALID_ROLE`) instead of
    FastAPI's generic 422. Unknown fields, `email` and `auth_user_id` included, are rejected: identity
    comes from the token (TC-US16A-25)."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    role: str | None = None


class ProfileOut(BaseModel):
    """What the frontend needs after the first login: who this is and which home screen to show."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole


class MeOut(ProfileOut):
    """GET /api/v1/me (SCRUM-105): as ProfileOut, but a user who never signed up may have no name."""

    full_name: str | None
