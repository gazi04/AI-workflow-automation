"""
Imported models are not used, in a traditional way, either way for SqlAlchemy they need to be imported to create the corresponding tables foreach model, for suppresing the lint error in ruff is used 'noqa'
"""

from database import Base, engine
from models import (
    User,  # noqa: F401
    UserSettings,  # noqa: F401
    Workflow,  # noqa: F401
    WorkflowRun,  # noqa: F401
    WorkflowLog,  # noqa: F401
    WorkflowTemplate,  # noqa: F401
    ConnectedAccount,  # noqa: F401
)


def create_tables():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")


if __name__ == "__main__":
    create_tables()
