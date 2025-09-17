from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

DATABASE_URL = "postgresql://gazi:gazi2004@localhost:5432/workflowDB"

# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create a SessionLocal class to get a new session for each request
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all your models
Base = declarative_base()

# Dependency to get a new database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
