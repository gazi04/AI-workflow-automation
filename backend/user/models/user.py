from core.database import Base
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional, TYPE_CHECKING

import uuid

if TYPE_CHECKING:
    from auth.models.connected_account import ConnectedAccount
    from auth.models.refresh_token import RefreshToken
    from user.models.user_settings import UserSettings
    from workflow.models.workflow import Workflow
    from workflow.models.workflow_template import WorkflowTemplate


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    connected_accounts: Mapped[List["ConnectedAccount"]] = relationship(
        "auth.models.connected_account.ConnectedAccount",
        back_populates="user", cascade="all, delete-orphan"
    )
    workflows: Mapped[List["Workflow"]] = relationship(
        "workflow.models.workflow.Workflow",
        back_populates="user", cascade="all, delete-orphan"
    )
    workflow_templates: Mapped[List["WorkflowTemplate"]] = relationship(
        "workflow.models.workflow_template.WorkflowTemplate",
        back_populates="created_by_user"
    )
    settings: Mapped[Optional["UserSettings"]] = relationship(
        "user.models.user_settings.UserSettings",
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "auth.models.refresh_token.RefreshToken",
        back_populates="user", cascade="all, delete-orphan"
    )
