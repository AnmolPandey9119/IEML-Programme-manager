from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# Some hosts hand out "postgres://..." but SQLAlchemy 2 only understands "postgresql://..."
DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

_connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
engine = create_engine(
    DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True
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