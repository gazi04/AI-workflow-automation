from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class GmailHeader(BaseModel):
    name: str
    value: str


class GmailMessagePartBody(BaseModel):
    size: int
    data: Optional[str] = None
    attachment_id: Optional[str] = Field(None, alias="attachmentId")


class GmailMessagePart(BaseModel):
    part_id: str = Field(..., alias="partId")
    mime_type: str = Field(..., alias="mimeType")
    filename: Optional[str] = None
    headers: List[GmailHeader] = Field(default_factory=list)
    body: Optional[GmailMessagePartBody] = None
    # Recursive relationship for multipart emails
    parts: List["GmailMessagePart"] = Field(default_factory=list)


class GmailMessage(BaseModel):
    id: str
    thread_id: str = Field(..., alias="threadId")
    label_ids: List[str] = Field(default_factory=list, alias="labelIds")
    snippet: str
    history_id: str = Field(..., alias="historyId")
    internal_date: str = Field(..., alias="internalDate")
    payload: GmailMessagePart
    size_estimate: int = Field(..., alias="sizeEstimate")

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",  # Ignore extra fields Google might add in the future
    )
