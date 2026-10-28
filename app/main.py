from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  (tables register hone ke liye)
from .database import Base, engine
from .migrate import add_missing_columns
from .routers import applications, auth, events, exports, groups, public, sessions, setup, speakers, team


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    add_missing_columns()
    yield


app = FastAPI(title="Session, Speaker & List Management System", lifespan=lifespan)


# The public agenda must be readable from any event website. GET only, no cookies and no custom headers,
# so the authenticated team API cannot be called from another origin.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=[], allow_credentials=False)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(events.router)
app.include_router(setup.router)
app.include_router(team.router)
app.include_router(speakers.router)
app.include_router(sessions.router)
app.include_router(groups.router)
app.include_router(exports.router)
app.include_router(groups.public)
app.include_router(public.router)
app.include_router(speakers.media)
app.include_router(applications.router)
app.include_router(applications.public)

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND.exists():  # sabse last mein mount, taaki /api routes pehle match hon
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")