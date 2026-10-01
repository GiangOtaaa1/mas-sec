# agents/worker1_research.py
from langgraph.prebuilt import create_react_agent
from config import get_llm
from tools.research_tools import search_information

WORKER1_PROMPT = (
    "You are Worker 1 (Research Agent). Your primary role is to find and research information.\n"
    "Always use the 'search_information' tool to find accurate data before answering.\n"
    "Provide a concise and direct answer based ONLY on the tool's output.\n"
    "CRITICAL RULE: Do NOT ask follow-up questions. Just provide the answer and stop."
)

def get_worker1():
    llm = get_llm(temperature=0.2)
    tools = [search_information]
    return create_react_agent(llm, tools)