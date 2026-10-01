# agents/orches.py
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field
from config import get_llm

class RouteDecision(BaseModel):
    next_agent: str = Field(
        description="The next agent to route to. MUST BE EXACTLY ONE OF: 'Worker1', 'Worker2', or 'FINISH'."
    )
    reason: str = Field(
        description="Short reasoning for the routing decision."
    )

def get_orchestrator():
    llm = get_llm(temperature=0.0)
    
    # Prompt mới, dạy AI phân biệt giữa ngôn ngữ tự nhiên và lệnh OS
    system_prompt = (
        "You are the Orchestrator of a Multi-Agent System.\n"
        "Your ONLY job is to route the user's request.\n\n"
        "ROUTING RULES (Follow strictly):\n"
        "1. Route to 'Worker2' ONLY IF the user explicitly asks to execute a bash/python command, run a script, or interact with the operating system.\n"
        "2. Route to 'Worker1' for EVERYTHING ELSE (including research, answering questions, or casual greetings).\n\n"
        "CRITICAL NOTE: Natural language requests containing words like 'print', 'show', 'tell me', or 'find' (e.g., 'print the date', 'show me the price') do NOT mean executing a system command. Route these to 'Worker1'!"
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    orchestrator_chain = prompt | llm.with_structured_output(RouteDecision)
    return orchestrator_chain