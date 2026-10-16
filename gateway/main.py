from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

if __package__:
    from .auth import create_access_token, get_current_user, require_role
    from .middleware import SecurityAuditMiddleware
else:
    from auth import create_access_token, get_current_user, require_role
    from middleware import SecurityAuditMiddleware

app = FastAPI(
    title="MAS Security Gateway",
    description="Cổng giao tiếp an toàn (Lớp 1) cho hệ thống Đa tác tử",
    version="1.0.0"
)

# Gắn Middleware bảo mật và Audit Log
app.add_middleware(SecurityAuditMiddleware)
router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class PromptRequest(BaseModel):
    prompt: str


# 1. Endpoint cấp phát Token (Mô phỏng xác thực)
@router.post("/api/v1/auth/token")
def login(form_data: LoginRequest):
    # Trong thực tế sẽ check DB, đây là hardcode demo cho đồ án
    if form_data.username == "admin" and form_data.password == "admin123":
        token = create_access_token({"sub": "admin", "role": "admin"})
        return {"access_token": token, "token_type": "bearer", "role": "admin"}
    elif form_data.username == "guest" and form_data.password == "guest123":
        token = create_access_token({"sub": "guest", "role": "guest"})
        return {"access_token": token, "token_type": "bearer", "role": "guest"}
    raise HTTPException(status_code=400, detail="Invalid username or password")

# 2. Endpoint for user requests (Forward to Moderator Agent)
@router.post("/api/v1/agent/chat")
def proxy_to_moderator(payload: PromptRequest, current_user: dict = Depends(get_current_user)):
    """
    Điểm tiếp nhận yêu cầu từ người dùng.
    Sau khi qua Gateway, request sẽ được chuyển tiếp vào Moderator Agent (Lớp 2).
    """
    user_role = current_user["role"]
    user_name = current_user["username"]

    # Tại đây Gateway sẽ đẩy payload qua LangGraph Workflow
    return {
        "status": "FORWARDED_TO_MODERATOR",
        "user": user_name,
        "role": user_role,
        "received_prompt": payload.prompt,
        "message": "Request passed FastAPI Gateway security checks."
    }

# 3. Endpoint for admin-only workspace purge (RBAC enforced)
@router.delete("/api/v1/admin/purge-workspace")
def admin_purge(current_user: dict = Depends(require_role("admin"))):
    """
    Only accessible by users with the 'admin' role. This endpoint purges the workspace and is intended for administrative purposes.
    """
    return {
        "status": "SUCCESS",
        "message": "Workspace purged by authorized admin.",
        "executed_by": current_user["username"]
    }

app.include_router(router)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@app.get("/", include_in_schema=False)
async def home():
    return RedirectResponse(url="/login.html")


app.mount("/", StaticFiles(directory=WEB_DIR), name="web")