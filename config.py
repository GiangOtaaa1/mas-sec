# config.py
import os
from langchain_ollama import ChatOllama

class Config:
    # 1. Configuration for Ollama LLM
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://172.22.32.1:11434")
    MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:7b")
    DEFAULT_TEMPERATURE = 0.0

    # 2. Workspace Isolation Configuration
    WORKSPACE_BASE_DIR = os.getenv("WORKSPACE_BASE_DIR", "./workspace/users")

    # 3. Docker Sandbox Configuration
    DOCKER_IMAGE = "python:3.9-slim"
    EXECUTION_TIMEOUT = 10 

def get_llm(temperature=Config.DEFAULT_TEMPERATURE):
    """Initialize and return a ChatOllama instance with the specified temperature."""
    return ChatOllama(
        base_url=Config.OLLAMA_BASE_URL,
        model=Config.MODEL_NAME,
        temperature=temperature
    )