# api/routes.py
import traceback
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage, HumanMessage
from graph.workflow import build_graph
from api.schemas import ChatRequest, ChatResponse, ApproveRequest
from gateway.auth import get_current_user, require_role

router = APIRouter()
app_graph = build_graph()

pending_approvals: dict[str, str] = {}
thread_owners: dict[str, str] = {}

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        thread_id = request.thread_id
        username = current_user["username"]
        owner = thread_owners.get(thread_id)
        if owner is not None and owner != username:
            raise HTTPException(status_code=403, detail="Thread belongs to another user.")
        thread_owners[thread_id] = username

        inputs = {
            "messages": [HumanMessage(content=request.message)],
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


@router.post("/approve")
async def approve_action(
    request: ApproveRequest,
    current_user: dict = Depends(require_role("admin")),
):
    try:
        target_thread = request.thread_id
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
        return {"response": response}
        
    except Exception as e:
        print("=== LỖI TẠI API APPROVE ===")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi Backend API: {str(e)}")