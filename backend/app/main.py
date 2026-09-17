from fastapi import FastAPI

from app.event.router import router as event_router

app = FastAPI(title="ConnectSphere Event Planner")

app.include_router(event_router)
