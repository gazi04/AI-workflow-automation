"""
This file acts as a "Manifest" for SQLAlchemy.
And can be used in the case where we want to import all the models but at the same time keep a clean code.
"""

from core.database import Base

from auth.models import ConnectedAccount, RefreshToken
from processed_messages.models import ProcessedMessages
from user.models.user import User
from workflow.models.workflow import Workflow
