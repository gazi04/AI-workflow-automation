from pydantic import BaseModel, Field
from typing import List, Optional


class IntegrationStatus(BaseModel):
    provider: str = Field(
        ..., description="The name of the integration (e.g., 'google', 'discord')"
    )
    is_connected: bool = Field(
        ..., description="True if the user has connected this account"
    )
    email: Optional[str] = Field(
        None, description="The email associated with the connected account"
    )
    needs_reconnect: bool = Field(
        ..., description="True if tokens are invalid and user must log in again"
    )


class ConnectionStatusResponse(BaseModel):
    integrations: List[IntegrationStatus]


SUPPORTED_PROVIDERS = ["google"]
