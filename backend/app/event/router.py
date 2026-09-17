from fastapi import APIRouter

from app.event.service import event_service

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/health")
def health() -> str:
    return event_service.health()
