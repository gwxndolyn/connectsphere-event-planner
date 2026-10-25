import uuid

from pydantic import BaseModel, ConfigDict, computed_field, field_validator

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
    roles: list[UserRole]

    @field_validator("roles")
    @classmethod
    def in_type_order(cls, roles: list[UserRole]) -> list[UserRole]:
        """Every held role, in the role type's order whatever order they're stored in (TC-US16B-07)."""
        order = list(UserRole)
        return sorted(roles, key=order.index)

    # DECISION-PENDING: SCRUM-121 removes `role` once the frontend reads `roles` (PR #86 review).
    @computed_field
    @property
    def role(self) -> UserRole:
        """The first held role, so the frontend's single-role reads keep working until SCRUM-121."""
        return self.roles[0]


class MeOut(ProfileOut):
    """GET /api/v1/me (SCRUM-105): as ProfileOut, but a user who never signed up may have no name."""

    full_name: str | None
