from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
from fastapi.responses import FileResponse, RedirectResponse
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
def login(form_data: LoginRequest, request: Request, response: Response):
    role = None
    # Trong thực tế sẽ check DB, đây là hardcode demo cho đồ án
    if form_data.username == "admin" and form_data.password == "admin123":
        role = "admin"
    elif form_data.username == "guest" and form_data.password == "guest123":
        role = "guest"
    if role is None:
        raise HTTPException(status_code=400, detail="Invalid username or password")

    token = create_access_token({"sub": form_data.username, "role": role})
    response.set_cookie(
        key="mas_token",
        value=token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=30 * 60,
        path="/",
    )
    return {"access_token": token, "token_type": "bearer", "role": role}

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


@router.post("/api/v1/auth/logout", status_code=204)
def logout():
    response = Response(status_code=204)
    response.delete_cookie("mas_token", path="/")
    return response


WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@router.get("/admin.html", include_in_schema=False)
def admin_dashboard(_: dict = Depends(require_role("admin"))):
    return FileResponse(WEB_DIR / "admin.html")


@router.get("/guest.html", include_in_schema=False)
def guest_dashboard(_: dict = Depends(get_current_user)):
    return FileResponse(WEB_DIR / "guest.html")


app.include_router(router)


@app.get("/", include_in_schema=False)
async def home():
    return RedirectResponse(url="/login.html")


app.mount("/", StaticFiles(directory=WEB_DIR), name="web")