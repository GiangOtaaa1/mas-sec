# api/schemas.py
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    role: str = "guest"
    thread_id: str = "thread_1"  # Used to track the paused session

class ChatResponse(BaseModel):
    response: str
    status: str = "COMPLETED"

class ApproveRequest(BaseModel):
    thread_id: str
    is_approved: bool