from contextlib import contextmanager
from typing import Iterator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker


from core.setup_logging import setup_logger
from .config_loader import settings


engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# get_db is used in FastAPI
def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        setup_logger("DB config").error(f"Unhandled error occurred: \n{e}")
        raise e
    finally:
        db.close()


# db_session is used for manual use (like in scripts, orchestration, etc.)
@contextmanager
def db_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        setup_logger("DB config").error(f"Unhandled error occurred: \n{e}")
        raise e
    finally:
        db.close()
