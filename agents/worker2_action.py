# agents/worker2_action.py
from langgraph.prebuilt import create_react_agent
from config import get_llm
from tools.action_tools import execute_command

WORKER2_PROMPT = (
    "You are Worker 2 (Action Agent). Your primary role is to execute system commands.\n"
    "Always use the 'execute_command' tool to perform the action requested by the user.\n"
    "Report the exact execution result back to the user clearly.\n"
    "CRITICAL RULE: Do NOT ask follow-up questions. Just provide the result and stop."
)

def get_worker2():
    llm = get_llm(temperature=0.0)
    tools = [execute_command]
    return create_react_agent(llm, tools)