from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict


class UserSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timezone: str
    default_llm_provider: str
    notification_preferences: Dict[str, bool]


class UserSettingsUpdate(BaseModel):
    """Partial update — every field optional; only provided keys are written."""

    timezone: Optional[str] = None
    default_llm_provider: Optional[str] = None
    notification_preferences: Optional[Dict[str, bool]] = None
