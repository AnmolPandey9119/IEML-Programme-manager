import asyncio
import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  (tables register hone ke liye)
from .database import Base, engine
from .migrate import add_missing_columns
from .routers import applications, auth, events, exports, groups, public, sessions, setup, speakers, team


log = logging.getLogger("startup")
_db_ready = threading.Event()
_db_booting = threading.Event()  # sirf tab set hota hai jab lifespan ne background init shuru kiya


def _init_db() -> None:
    """DB setup background mein chalta hai taaki server ka port turant khul jaye (Render ko port chahiye).
    Remote / cold-start database par ye kuch seconds le sakta hai, isliye retry ke saath."""
    for attempt in range(1, 11):
        try:
            Base.metadata.create_all(bind=engine)
            add_missing_columns()
            _db_ready.set()
            log.warning("Database ready")
            return
        except Exception as exc:  # noqa: BLE001
            log.warning("Database init attempt %s failed: %s", attempt, exc)
            time.sleep(min(3 * attempt, 15))
    log.error("Database init failed after retries")


@asynccontextmanager
async def lifespan(_: FastAPI):
    _db_booting.set()
    threading.Thread(target=_init_db, daemon=True).start()
    # Fast DB ho to port khulne se pehle hi ready (best case); slow ho to 3s baad port khul jata hai, setup peeche chalta rehta hai.
    await asyncio.to_thread(_db_ready.wait, 3)
    yield


app = FastAPI(title="Session, Speaker & List Management System", lifespan=lifespan)


# The public agenda must be readable from any event website. GET only, no cookies and no custom headers,
# so the authenticated team API cannot be called from another origin.
app.add_middleware(GZipMiddleware, minimum_size=800)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=[], allow_credentials=False)


@app.middleware("http")
async def wait_for_db(request: Request, call_next):
    if _db_booting.is_set() and not _db_ready.is_set() and request.url.path.startswith("/api"):
        return JSONResponse({"detail": "Server is starting up, please retry in a few seconds."}, status_code=503)
    return await call_next(request)


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