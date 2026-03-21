from collections.abc import Generator

from sqlalchemy.orm import Session

from backend.db.session import SessionLocal


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
