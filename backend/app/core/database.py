import enum
from collections.abc import Generator

from sqlalchemy import Enum, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# pool_pre_ping: Supabase's pooler drops idle connections; test each one before use.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """A Postgres enum type that stores each member's value ("in_person"), not its name ("IN_PERSON")."""
    return Enum(enum_cls, name=name, values_callable=lambda members: [m.value for m in members])


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
