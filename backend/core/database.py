from contextlib import contextmanager
from typing import Iterator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from core.setup_logging import setup_logger
from .config_loader import settings


engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


@contextmanager
def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        setup_logger("core/database.py").error(f"Unhandled error occurred: \n{e}")
        raise e
    finally:
        db.close()
