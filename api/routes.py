# api/routes.py
import traceback
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage
from graph.workflow import build_graph
from api.schemas import ChatRequest, ChatResponse, ApproveRequest

router = APIRouter()
app_graph = build_graph()

# --- TICKET QUEUE ---
# Archive thread_id of users who are waiting for approval
pending_approvals = []

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        inputs = {
            "messages": [HumanMessage(content=request.message)],
            "user_role": request.role
        }
        config = {"configurable": {"thread_id": request.thread_id}}
        
        final_state = app_graph.invoke(inputs, config=config)
        
        state_snapshot = app_graph.get_state(config)
        if state_snapshot.next:
            # If graph is paused, add the thread_id to the pending approvals list
            if request.thread_id not in pending_approvals:
                pending_approvals.append(request.thread_id)
                
            return ChatResponse(
                response="[HITL WAIT] Execution is paused. Admin approval is required to run this command.",
                status="WAITING_FOR_APPROVAL"
            )
        
        last_message = final_state["messages"][-1].content
        return ChatResponse(response=last_message, status="COMPLETED")
    
    except Exception as e:
        print("=== LỖI TẠI API CHAT ===")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.post("/approve")
async def approve_action(request: Request):
    try:
        # 1. Find ticket that is waiting for approval
        if pending_approvals:
            # Take the last thread_id from the pending approvals list (FIFO)
            target_thread = pending_approvals.pop(0)
        else:
            return JSONResponse(
                status_code=400, 
                content={"response": "Không có phiên làm việc nào đang chờ phê duyệt!"}
            )
            
        config = {"configurable": {"thread_id": target_thread}}
        
        # 2. Check if the graph is still paused for this thread_id
        state_snapshot = app_graph.get_state(config)
        if not state_snapshot.next:
            return JSONResponse(
                status_code=400, 
                content={"response": "Phiên làm việc này đã được xử lý hoặc đã hết hạn."}
            )
        
        # 3. Resume the graph execution for this thread_id
        final_state = app_graph.invoke(None, config)
        
        last_message = final_state["messages"][-1].content
        return {"response": f"[HỆ THỐNG] Đã phê duyệt lệnh thành công!\nKết quả:\n{last_message}"}
        
        # 4. Errors handling
    except Exception as e:
        print("=== LỖI TẠI API APPROVE ===")
        traceback.print_exc()
        return JSONResponse(
            status_code=500, 
            content={"response": f"Lỗi Backend API: {str(e)}"}
        )