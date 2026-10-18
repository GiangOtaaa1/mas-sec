# api/routes.py
import traceback
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage, HumanMessage
from graph.workflow import build_graph
from api.schemas import (
    ApprovalStatusResponse,
    ApproveRequest,
    ChatRequest,
    ChatResponse,
    OpenClawChatRequest,
    PendingApprovalResponse,
)
from gateway.auth import get_current_user, require_role

router = APIRouter()
app_graph = build_graph()

pending_approvals: dict[str, str] = {}
thread_owners: dict[str, str] = {}
completed_results: dict[str, ApprovalStatusResponse] = {}

async def _run_chat(message: str, thread_id: str, current_user: dict) -> ChatResponse:
    try:
        username = current_user["username"]
        owner = thread_owners.get(thread_id)
        if owner is not None and owner != username:
            raise HTTPException(status_code=403, detail="Thread belongs to another user.")
        if thread_id in pending_approvals:
            raise HTTPException(
                status_code=409,
                detail="Thread is waiting for an admin decision; do not resubmit the request.",
            )
        thread_owners[thread_id] = username
        completed_results.pop(thread_id, None)

        inputs = {
            "messages": [HumanMessage(content=message)],
            "user_role": current_user["role"],
            "approval_granted": False,
        }
        config = {"configurable": {"thread_id": thread_id}}
        
        final_state = app_graph.invoke(inputs, config=config)
        
        state_snapshot = app_graph.get_state(config)
        if state_snapshot.next:
            pending_approvals[thread_id] = username
                
            return ChatResponse(
                response="[HITL WAIT] Execution is paused. Admin approval is required to run this command.",
                status="WAITING_FOR_APPROVAL"
            )
        
        last_message = final_state["messages"][-1].content
        return ChatResponse(response=last_message, status="COMPLETED")
    
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        print("=== LỖI TẠI API CHAT ===")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    return await _run_chat(request.message, request.thread_id, current_user)


@router.post("/v1/agent/chat", response_model=ChatResponse)
async def openclaw_chat_endpoint(
    request: OpenClawChatRequest,
    current_user: dict = Depends(get_current_user),
):
    return await _run_chat(request.prompt, request.thread_id, current_user)


@router.get("/approvals", response_model=list[PendingApprovalResponse])
async def list_pending_approvals(
    current_user: dict = Depends(require_role("admin")),
):
    approvals = []
    for thread_id, username in list(pending_approvals.items()):
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = app_graph.get_state(config)
        if not snapshot.next:
            pending_approvals.pop(thread_id, None)
            continue

        messages = snapshot.values.get("messages", [])
        request = next(
            (message.content for message in reversed(messages) if isinstance(message, HumanMessage)),
            "",
        )
        approvals.append(
            PendingApprovalResponse(
                thread_id=thread_id,
                username=username,
                request=request,
            )
        )
    return approvals


@router.get("/v1/agent/status/{thread_id}", response_model=ApprovalStatusResponse)
async def agent_status(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
):
    username = current_user["username"]
    owner = thread_owners.get(thread_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Thread was not found.")
    if owner != username:
        raise HTTPException(status_code=403, detail="Thread belongs to another user.")

    if thread_id in pending_approvals:
        return ApprovalStatusResponse(
            thread_id=thread_id,
            response="[HITL WAIT] Execution is paused. Admin approval is required.",
            status="WAITING_FOR_APPROVAL",
        )

    result = completed_results.get(thread_id)
    if result is None:
        raise HTTPException(status_code=409, detail="No completed approval result is available.")
    return result


@router.post("/approve")
async def approve_action(
    request: ApproveRequest,
    current_user: dict = Depends(require_role("admin")),
):
    target_thread = request.thread_id
    try:
        if target_thread not in pending_approvals:
            return JSONResponse(
                status_code=404,
                content={"response": "Không có phiên làm việc nào đang chờ phê duyệt"}
            )
            
        config = {"configurable": {"thread_id": target_thread}}
        
        state_snapshot = app_graph.get_state(config)
        if not state_snapshot.next:
            pending_approvals.pop(target_thread, None)
            return JSONResponse(
                status_code=409,
                content={"response": "Phiên làm việc này đã được xử lý hoặc đã hết hạn."}
            )
        
        app_graph.update_state(
            config,
            {"approval_granted": request.is_approved},
        )
        final_state = app_graph.invoke(None, config)
        pending_approvals.pop(target_thread, None)
        
        last_message = final_state["messages"][-1].content
        if request.is_approved:
            response = f"[HỆ THỐNG] Đã phê duyệt lệnh thành công!\nKết quả:\n{last_message}"
        else:
            response = f"[HỆ THỐNG] Đã từ chối lệnh.\n{last_message}"
        completed_results[target_thread] = ApprovalStatusResponse(
            thread_id=target_thread,
            response=response,
            status="COMPLETED",
        )
        return {"thread_id": target_thread, "response": response, "status": "COMPLETED"}
        
    except Exception as e:
        print("=== LỖI TẠI API APPROVE ===")
        traceback.print_exc()
        if target_thread in pending_approvals:
            pending_approvals.pop(target_thread, None)
            completed_results[target_thread] = ApprovalStatusResponse(
                thread_id=target_thread,
                response=(
                    "[HITL ERROR] Workflow continuation failed. An administrator "
                    "must inspect the server logs before retrying this action."
                ),
                status="FAILED",
            )
        raise HTTPException(status_code=500, detail=f"Lỗi Backend API: {str(e)}")