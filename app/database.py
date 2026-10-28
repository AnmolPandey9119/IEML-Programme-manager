from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# Some hosts hand out "postgres://..." but SQLAlchemy 2 only understands "postgresql://..."
DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

_connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {"connect_timeout": 15}
)
_is_sqlite = DATABASE_URL.startswith("sqlite")
if not _is_sqlite:
    # Dead connections ko TCP keepalive pakadta hai; pool_recycle Neon ke idle-suspend (5 min) se pehle purane
    # connection badal deta hai. Isse har request par extra "ping" round-trip (pool_pre_ping) bachta hai.
    _connect_args.update({"keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 3})
engine = create_engine(
    DATABASE_URL, connect_args=_connect_args,
    **({} if _is_sqlite else {"pool_size": 5, "max_overflow": 5, "pool_recycle": 240, "pool_timeout": 20}),
)
if DATABASE_URL.startswith("sqlite"):
    @sa_event.listens_for(engine, "connect")
    def _sqlite_fk(dbapi_con, _):
        dbapi_con.execute("PRAGMA foreign_keys=ON")  # prod (Postgres) jaisa behaviour

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()