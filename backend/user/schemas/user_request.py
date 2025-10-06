from pydantic import BaseModel


class UserRequest(BaseModel):
    text: str
