from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.user import service
from app.user.auth import TokenClaims
from app.user.dependencies import get_token_claims
from app.user.schemas import ProfileOut, ProfileWrite

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/profile", status_code=201, response_model=ProfileOut)
def create_profile(
    body: ProfileWrite,
    claims: TokenClaims = Depends(get_token_claims),
    db: Session = Depends(get_db),
) -> ProfileOut:
    """Called on a confirmed user's first login, after the token check answered PROFILE_REQUIRED."""
    return service.create_profile(db, claims, body)
