# tests/test_agents.py
import sys
import os

# Add the project root to python path to resolve imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage
from graph.workflow import build_graph

def run_test():
    print("=== INITIALIZING MULTI-AGENT WORKFLOW ===\n")
    graph = build_graph()
    
    # Test Case 1: Trigger Research (Worker 1)
    print("--- TEST 1: RESEARCH REQUEST ---")
    inputs1 = {"messages": [HumanMessage(content="Find information about LangGraph.")]}
    for output in graph.stream(inputs1, {"recursion_limit": 10}):
        for key, value in output.items():
            print(f"[{key.upper()}] node executed.")
            if "messages" in value:
                print(f"Response: {value['messages'][-1].content}\n")

    # Test Case 2: Trigger Action (Worker 2)
    print("\n--- TEST 2: ACTION REQUEST ---")
    inputs2 = {"messages": [HumanMessage(content="Execute a command to list files: ls -la")]}
    for output in graph.stream(inputs2, {"recursion_limit": 10}):
        for key, value in output.items():
            print(f"[{key.upper()}] node executed.")
            if "messages" in value:
                print(f"Response: {value['messages'][-1].content}\n")

if __name__ == "__main__":
    run_test()