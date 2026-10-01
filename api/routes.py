# api/routes.py
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage, AIMessage
from graph.workflow import build_graph
from api.schemas import ChatRequest, ChatResponse, ApproveRequest

router = APIRouter()
graph = build_graph()

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        inputs = {
            "messages": [HumanMessage(content=request.message)],
            "user_role": request.role
        }
        config = {"configurable": {"thread_id": request.thread_id}}
        
        # Execute workflow
        final_state = graph.invoke(inputs, config=config)
        
        # Check if graph is paused (waiting for human approval)
        state_snapshot = graph.get_state(config)
        if state_snapshot.next:
            return ChatResponse(
                response="[HITL WAIT] Execution is paused. Admin approval is required to run this command.",
                status="WAITING_FOR_APPROVAL"
            )
        
        last_message = final_state["messages"][-1].content
        return ChatResponse(response=last_message, status="COMPLETED")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.post("/approve", response_model=ChatResponse)
async def approve_endpoint(request: ApproveRequest):
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        state_snapshot = graph.get_state(config)
        
        # If nothing is paused
        if not state_snapshot.next:
            return ChatResponse(
                response="No pending actions require approval for this thread.", 
                status="COMPLETED"
            )
        
        if request.is_approved:
            # Resume execution by passing None
            final_state = graph.invoke(None, config=config)
            last_message = final_state["messages"][-1].content
            return ChatResponse(response=last_message, status="COMPLETED")
        else:
            # Inject rejection message and cancel execution
            cancel_msg = AIMessage(content="[HITL REJECTED] Admin rejected the execution.")
            graph.update_state(config, {"messages": [cancel_msg], "next_agent": "FINISH"}, as_node="worker2")
            
            # Resume after state modification
            graph.invoke(None, config=config)
            return ChatResponse(response="Execution was rejected and cancelled.", status="COMPLETED")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")