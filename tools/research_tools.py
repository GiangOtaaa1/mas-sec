# tools/research_tools.py
from langchain_core.tools import tool
from ddgs import DDGS
from security.audit import log_audit
from datetime import datetime  

@tool
def search_information(query: str) -> str:
    """Use this tool to search the internet for real-time news, facts, updates, and current events.
    Input should be a specific search query."""
    
    print(f"\n[🚀 WORKER 1 IS ONLINE] Searching internet for: '{query}'\n")
    log_audit("TOOL_USAGE", "worker1", f"Executed internet search for: {query}")
    
    try:
        results = DDGS().text(query, max_results=3)
        
        current_time = datetime.now().strftime("%A, %d/%m/%Y")
        
        if not results:
            return f"[System Note: Today is {current_time}]\nNo results found."
            
        formatted_results = [f"[System Note: Today is {current_time}]\nHere are the latest search results:"]
        
        for r in results:
            title = r.get('title', 'No Title')
            body = r.get('body', 'No Content')
            link = r.get('href', 'No Link')
            formatted_results.append(f"- Source: {title}\n  URL: {link}\n  Detail: {body}\n")
            
        return "\n".join(formatted_results)
        
    except Exception as e:
        return f"Internet Search failed: {str(e)}"