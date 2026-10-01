# graph/workflow.py
import operator
from typing import Annotated, TypedDict
from langchain_core.messages import AnyMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agents.orches import get_orchestrator
from agents.worker1_research import get_worker1, WORKER1_PROMPT
from agents.worker2_action import get_worker2, WORKER2_PROMPT
from security.moderator import moderate_request
from security.rbac import check_permission
from security.audit import log_audit

# 1. Update AgentState to include user_role
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    next_agent: str
    moderation_action: str
    user_role: str

def moderator_node(state: AgentState):
    """First line of defense: check user input for security risks."""
    last_message = state["messages"][-1].content
    mod_result = moderate_request(last_message)
    
    if mod_result.action != "ALLOW":
        reject_msg = AIMessage(
            content=f"[SECURITY ALERT] Request denied.\nAction: {mod_result.action}\nReason: {mod_result.reason}"
        )
        return {"messages": [reject_msg], "moderation_action": mod_result.action}
    
    return {"moderation_action": "ALLOW"}

def orchestrator_node(state: AgentState):
    """Orchestrator decides next step and enforces RBAC policy."""
    orchestrator_chain = get_orchestrator()
    result = orchestrator_chain.invoke({"messages": state["messages"]})
    next_target = result.next_agent
    
    # --- RBAC POLICY CHECK ENFORCEMENT ---
    user_role = state.get("user_role", "guest")
    if next_target in ["Worker1", "Worker2"]:
        is_allowed = check_permission(user_role, next_target)
        if not is_allowed:
            # Block the action and route to FINISH immediately
            reject_msg = AIMessage(
                content=f"[RBAC DENIED] Policy violation. Role '{user_role}' is not authorized to use {next_target}."
            )
            return {"messages": [reject_msg], "next_agent": "FINISH"}
            
    return {"next_agent": next_target}

def worker1_node(state: AgentState):
    agent = get_worker1()
    messages = [SystemMessage(content=WORKER1_PROMPT)] + state["messages"]
    result = agent.invoke({"messages": messages})
    return {"messages": result["messages"][-1:]}

def worker2_node(state: AgentState):
    agent = get_worker2()
    messages = [SystemMessage(content=WORKER2_PROMPT)] + state["messages"]
    result = agent.invoke({"messages": messages})
    return {"messages": result["messages"][-1:]}

def moderator_route(state: AgentState):
    if state.get("moderation_action") == "ALLOW":
        return "orchestrator"
    return END

def route_condition(state: AgentState):
    # Notice we use "FINISH" as our internal STOP signal, converting it to END
    if state.get("next_agent") == "Worker1":
        return "worker1"
    elif state.get("next_agent") == "Worker2":
        return "worker2"
    else:
        return END

def build_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("moderator", moderator_node)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("worker1", worker1_node)
    workflow.add_node("worker2", worker2_node)
    
    workflow.set_entry_point("moderator")
    
    workflow.add_conditional_edges("moderator", moderator_route, {"orchestrator": "orchestrator", END: END})
    workflow.add_conditional_edges("orchestrator", route_condition, {"worker1": "worker1", "worker2": "worker2", END: END})
    
    workflow.add_edge("worker1", "orchestrator")
    workflow.add_edge("worker2", "orchestrator")
    
    return workflow.compile()

def build_graph():
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(AgentState)
    
    workflow.add_node("moderator", moderator_node)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("worker1", worker1_node)
    workflow.add_node("worker2", worker2_node)
    
    workflow.set_entry_point("moderator")
    
    workflow.add_conditional_edges("moderator", moderator_route, {"orchestrator": "orchestrator", END: END})
    workflow.add_conditional_edges("orchestrator", route_condition, {"worker1": "worker1", "worker2": "worker2", END: END})
    
    # workflow.add_edge("worker1", "orchestrator")
    # workflow.add_edge("worker2", "orchestrator")

    workflow.add_edge("worker1", END)
    workflow.add_edge("worker2", END)
    
    # --- PHASE 7: HITL CONFIGURATION ---
    memory = MemorySaver()
    
    # Compile with memory and explicitly pause BEFORE worker2 starts
    return workflow.compile(
        checkpointer=memory, 
        interrupt_before=["worker2"]
    )

def moderator_node(state: AgentState):
    """First line of defense: check user input for security risks."""
    last_message = state["messages"][-1].content
    user_role = state.get("user_role", "unknown")
    
    mod_result = moderate_request(last_message)
    
    if mod_result.action != "ALLOW":
        # Log the blocked attack
        log_audit("MODERATOR_BLOCKED", user_role, f"Action: {mod_result.action} | Reason: {mod_result.reason}")
        
        reject_msg = AIMessage(
            content=f"[SECURITY ALERT] Request denied.\nAction: {mod_result.action}\nReason: {mod_result.reason}"
        )
        return {"messages": [reject_msg], "moderation_action": mod_result.action}
    
    # Log allowed request
    log_audit("MODERATOR_ALLOWED", user_role, "Prompt passed security check.")
    return {"moderation_action": "ALLOW"}

def orchestrator_node(state: AgentState):
    """Orchestrator decides next step and enforces RBAC policy."""
    orchestrator_chain = get_orchestrator()
    result = orchestrator_chain.invoke({"messages": state["messages"]})
    next_target = result.next_agent
    
    user_role = state.get("user_role", "guest")
    
    if next_target in ["Worker1", "Worker2"]:
        is_allowed = check_permission(user_role, next_target)
        if not is_allowed:
            # Log RBAC violation
            log_audit("RBAC_DENIED", user_role, f"Denied access to {next_target}.")
            
            reject_msg = AIMessage(
                content=f"[RBAC DENIED] Policy violation. Role '{user_role}' is not authorized to use {next_target}."
            )
            return {"messages": [reject_msg], "next_agent": "FINISH"}
            
    # Log successful routing
    log_audit("ROUTING", user_role, f"Orchestrator assigned task to {next_target}.")
    return {"next_agent": next_target}