from datetime import datetime, timedelta
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional


class WorkflowRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="The Prefect run id.")
    name: str = Field(..., description="The name of the flow run.")
    deployment_id: Optional[UUID] = Field(
        None, description="The ID of the associated deployment."
    )
    state_name: Optional[str] = Field(
        None, description="The name of the current flow run state."
    )
    start_time: Optional[datetime] = Field(
        default=None, description="The actual start time."
    )
    total_run_time: float = Field(
        0.0,
        description="Total run time in seconds.",
    )

    @field_validator("total_run_time", mode="before")
    @classmethod
    def transform_timedelta(cls, v):
        """
        Translates a timedelta object (from the original FlowRun)
        into a float (seconds) for easier JSON handling.
        """
        if isinstance(v, timedelta):
            return v.total_seconds()
        return v
