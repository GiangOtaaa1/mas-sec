# config.py
import os
import platform
import socket
import struct
from langchain_ollama import ChatOllama


def _is_wsl() -> bool:
    return bool(os.getenv("WSL_DISTRO_NAME")) or "microsoft" in platform.release().lower()


def _get_wsl_gateway(route_file: str = "/proc/net/route") -> str:
    try:
        with open(route_file, encoding="ascii") as routes:
            next(routes, None)
            default_routes = []
            for line in routes:
                fields = line.split()
                if len(fields) < 8 or fields[1] != "00000000":
                    continue
                flags = int(fields[3], 16)
                if flags & 0x2:
                    default_routes.append(
                        (int(fields[6]), socket.inet_ntoa(struct.pack("<I", int(fields[2], 16))))
                    )
    except OSError as exc:
        raise RuntimeError("Unable to read the WSL default route from /proc/net/route.") from exc

    if not default_routes:
        raise RuntimeError("Unable to determine the WSL default gateway from /proc/net/route.")
    return min(default_routes)[1]


def _default_ollama_base_url() -> str:
    host = _get_wsl_gateway() if _is_wsl() else "localhost"
    return f"http://{host}:11434"


class Config:
    # 1. Configuration for Ollama LLM
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL") or _default_ollama_base_url()
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