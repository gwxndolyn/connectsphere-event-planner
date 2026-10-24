from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import DomainError, domain_error_handler
from app.equipment.router import events_router as equipment_events_router
from app.equipment.router import me_router as equipment_me_router
from app.equipment.router import router as equipment_router
from app.equipment.router import types_router as equipment_types_router
from app.event.router import router as event_router
from app.event.router import v1_router as event_v1_router
from app.event.request_router import coordinators_router as event_request_coordinators_router
from app.event.request_router import me_router as event_request_me_router
from app.event.request_router import router as event_request_router
from app.registration.router import events_router as registration_events_router
from app.registration.router import me_router as registration_me_router
from app.registration.router import router as registration_router
from app.user.auth import warn_if_dev_headers_enabled
from app.user.router import me_router as auth_me_router
from app.user.router import router as auth_router
from app.venue.booking_router import events_router as venue_booking_events_router
from app.venue.booking_router import router as venue_booking_router
from app.venue.router import router as venue_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    warn_if_dev_headers_enabled()
    yield


app = FastAPI(title="ConnectSphere Event Planner", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(DomainError, domain_error_handler)

app.include_router(event_router)
app.include_router(event_v1_router)
app.include_router(registration_router)
app.include_router(registration_events_router)
app.include_router(registration_me_router)
app.include_router(event_request_router)
app.include_router(event_request_me_router)
app.include_router(event_request_coordinators_router)
app.include_router(venue_router)
app.include_router(venue_booking_router)
app.include_router(venue_booking_events_router)
app.include_router(equipment_types_router)
app.include_router(equipment_router)
app.include_router(equipment_events_router)
app.include_router(equipment_me_router)
app.include_router(auth_router)
app.include_router(auth_me_router)
