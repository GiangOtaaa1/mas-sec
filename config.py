# config.py
import os
from langchain_ollama import ChatOllama

class Config:
    # 1. Cấu hình LLM (Phase 1)
    # Lấy từ biến môi trường, nếu không có thì dùng giá trị mặc định (IP WSL của bạn)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://172.22.32.1:11434")
    MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:7b")
    DEFAULT_TEMPERATURE = 0.0

    # 2. Cấu hình Workspace (Dành cho Phase 5 - Path Validation)
    WORKSPACE_BASE_DIR = os.getenv("WORKSPACE_BASE_DIR", "./workspace/users")

    # 3. Cấu hình Docker Sandbox (Dành cho Phase 6)
    DOCKER_IMAGE = "python:3.9-slim"
    EXECUTION_TIMEOUT = 10 # Giới hạn 10 giây cho mỗi lệnh thực thi

def get_llm(temperature=Config.DEFAULT_TEMPERATURE):
    """Khởi tạo và trả về LLM dùng chung cho toàn hệ thống."""
    return ChatOllama(
        base_url=Config.OLLAMA_BASE_URL,
        model=Config.MODEL_NAME,
        temperature=temperature
    )