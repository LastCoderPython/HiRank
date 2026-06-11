from pydantic import BaseModel, Field
from typing import Optional, List


class ChatMessage(BaseModel):
    model_config = {"extra": "forbid"}
    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    model_config = {"extra": "forbid"}
    message: str = Field(..., description="User message/query")
    session_id: Optional[str] = Field(None, description="Session identifier")
    history: Optional[List[ChatMessage]] = Field(
        default_factory=list,
        description="Chat history for context"
    )
