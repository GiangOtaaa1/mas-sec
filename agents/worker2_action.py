from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from config import get_llm
from sandbox.manager import execute_in_docker
from datetime import datetime

current_date = datetime.now().strftime("%Y-%m-%d")

WORKER2_PROMPT = (
    "You are Worker 2 (Action Agent). Your primary role is to execute system commands.Today's date is {current_date}\n"
    "Always use the 'execute_command' tool to perform the action requested by the user.\n"
    "Report the exact execution result back to the user clearly.\n"
    "CRITICAL RULE: Do NOT ask follow-up questions. Just provide the result and stop."
)

def get_worker2(username: str):
    
    @tool
    def execute_command(command: str) -> str:
        """Use this tool to execute system commands in a secure sandbox environment."""
        return execute_in_docker(command, username=username)

    llm = get_llm(temperature=0.0)
    tools = [execute_command]
    
    return create_react_agent(llm, tools)