from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import DomainError, domain_error_handler
from app.event.router import router as event_router
from app.event.router import v1_router as event_v1_router
from app.registration.router import events_router as registration_events_router
from app.registration.router import router as registration_router

app = FastAPI(title="ConnectSphere Event Planner")

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
