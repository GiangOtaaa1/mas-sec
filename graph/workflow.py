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

# 1. State Definition
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    next_agent: str
    moderation_action: str
    user_role: str

# 2. Node Functions
def moderator_node(state: AgentState):
    last_message = state["messages"][-1].content
    user_role = state.get("user_role", "unknown")
    
    mod_result = moderate_request(last_message)
    if mod_result.action != "ALLOW":
        log_audit("MODERATOR_BLOCKED", user_role, f"Action: {mod_result.action} | Reason: {mod_result.reason}")
        reject_msg = AIMessage(content=f"[SECURITY ALERT] Request denied.\nAction: {mod_result.action}\nReason: {mod_result.reason}")
        return {"messages": [reject_msg], "moderation_action": mod_result.action}
    
    log_audit("MODERATOR_ALLOWED", user_role, "Prompt passed security check.")
    return {"moderation_action": "ALLOW"}

def orchestrator_node(state: AgentState):
    orchestrator_chain = get_orchestrator()
    result = orchestrator_chain.invoke({"messages": state["messages"]})
    next_target = result.next_agent
    
    user_role = state.get("user_role", "guest")
    
    # 1. Check Static RBAC 
    if next_target in ["Worker1", "Worker2"]:
        is_allowed = check_permission(user_role, next_target)
        if not is_allowed:
            log_audit("RBAC_DENIED", user_role, f"Denied access to {next_target}.")
            reject_msg = AIMessage(content=f"[RBAC DENIED] Policy violation. Role '{user_role}' is not authorized to use {next_target}.")
            return {"messages": [reject_msg], "next_agent": "FINISH"}
            
    # Prevent Guest from executing dangerous commands in Worker2
    if next_target == "Worker2" and user_role == "guest":
        prompt = state["messages"][-1].content.lower()
        
        # Blacklist
        forbidden_guest_cmds = [
            "whoami", "id", "uname", "env", "history",              # Recon user/OS
            "ifconfig", "ip a", "ipconfig", "netstat", "ping",      # Recon network
            "ps", "top", "htop", "df", "du",                        # Recon process/disk
            "chmod", "chown", "rm ", "kill", "reboot", "shutdown",  # Dangerous system commands
            "apt", "yum", "apk", "wget", "curl", "systemctl"        # iNstallation or service management
        ]
        
        if any(cmd in prompt for cmd in forbidden_guest_cmds):
            log_audit("GUEST_RECON_BLOCKED", user_role, "Blocked Guest from recon/system commands.")
            reject_msg = AIMessage(content="[SECURITY ALERT] Request denied. Guest accounts are STRICTLY FORBIDDEN from executing reconnaissance or system-critical commands.")
            return {"messages": [reject_msg], "next_agent": "FINISH"}  # Chuyển thẳng về Đích
            
    log_audit("ROUTING", user_role, f"Orchestrator assigned task to {next_target}.")
    return {"next_agent": next_target}

def worker1_node(state: AgentState):
    agent = get_worker1()
    messages = [SystemMessage(content=WORKER1_PROMPT)] + state["messages"]
    result = agent.invoke({"messages": messages})
    return {"messages": result["messages"][-1:]}

def worker2_node(state: AgentState):
    current_user = state.get("user_role", "guest")
    agent = get_worker2(username=current_user)
    messages = [SystemMessage(content=WORKER2_PROMPT)] + state["messages"]
    result = agent.invoke({"messages": messages})
    return {"messages": result["messages"][-1:]}

# Virtual Node for HITL (Human-in-the-Loop) Approval
def hitl_node(state: AgentState):
    """Approval checkpoint. The graph will pause HERE if the command is considered risky."""
    user_role = state.get("user_role", "unknown")
    log_audit("HITL_APPROVED", user_role, "Admin approved manual execution.")
    return {} 

# 3. Routing Condition Functions
def moderator_route(state: AgentState):
    if state.get("moderation_action") == "ALLOW":
        return "orchestrator"
    return END

def route_condition(state: AgentState):
    next_agent = state.get("next_agent")
    
    if next_agent == "Worker1":
        return "worker1"
        
    elif next_agent == "Worker2":
       # Context-aware security check
        prompt = state["messages"][-1].content.lower()
        
        # Keywords for harmless file operations
        safe_keywords = ["create", "read", "write", "file", "txt", "cat", "echo", "touch", "ls"]
        # Keywords for potentially dangerous operations
        danger_keywords = ["rm ", "delete", "kill", "reboot", "chmod", "chown", "apt", "install", "wget", "curl"]
        
        is_safe = any(kw in prompt for kw in safe_keywords)
        is_danger = any(kw in prompt for kw in danger_keywords)
        
        # Routing decision:
        if is_safe and not is_danger:
            return "worker2"   
        else:
            return "hitl_node" 
            
    return END

# 4. Graph Construction
def build_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("moderator", moderator_node)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("worker1", worker1_node)
    workflow.add_node("worker2", worker2_node)
    workflow.add_node("hitl_node", hitl_node) 
    
    workflow.set_entry_point("moderator")
    
    workflow.add_conditional_edges("moderator", moderator_route, {"orchestrator": "orchestrator", END: END})
    
    # Cập nhật ngã rẽ từ Orchestrator
    workflow.add_conditional_edges(
        "orchestrator", 
        route_condition, 
        {
            "worker1": "worker1", 
            "worker2": "worker2", 
            "hitl_node": "hitl_node", # Add the approval checkpoint branch
            END: END
        }
    )
    
    # Connect the approval checkpoint to Worker 2
    workflow.add_edge("hitl_node", "worker2") 
    
    workflow.add_edge("worker1", END)
    workflow.add_edge("worker2", END)
    
    memory = MemorySaver()
    
    # Move the interrupt point from Worker 2 to the approval checkpoint
    return workflow.compile(
        checkpointer=memory, 
        interrupt_before=["hitl_node"] 
    )