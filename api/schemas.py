# api/schemas.py
from typing import Literal

from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "thread_1"  # Used to track the paused session


class OpenClawChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)
    thread_id: str = Field(min_length=1, max_length=128)


class ChatResponse(BaseModel):
    response: str
    status: str = "COMPLETED"


class ApprovalStatusResponse(BaseModel):
    thread_id: str
    response: str
    status: Literal["WAITING_FOR_APPROVAL", "COMPLETED", "FAILED"]


class PendingApprovalResponse(BaseModel):
    thread_id: str
    username: str
    request: str


class ApproveRequest(BaseModel):
    thread_id: str
    is_approved: bool