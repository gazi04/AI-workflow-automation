"""
This file acts as a "Manifest" for SQLAlchemy.
And can be used in the case where we want to import all the models but at the same time keep a clean code.
"""

from core.database import Base # noqa: F401

from auth.models import ConnectedAccount, RefreshToken # noqa: F401 
from processed_messages.models import ProcessedMessages # noqa: F401 
from user.models.user import User # noqa: F401
from workflow.models.workflow import Workflow # noqa: F401
