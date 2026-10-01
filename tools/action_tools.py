# tools/action_tools.py
from langchain_core.tools import tool
from security.workspace import validate_command_paths
from sandbox.manager import execute_in_docker
from security.audit import log_audit

@tool
def execute_command(command: str) -> str:
    """Use this tool to execute a system command (e.g., bash, python script).
    Input is the command string to be executed."""
    
    # 1. Enforce Workspace Isolation Policy
    validation_error = validate_command_paths(command)
    if validation_error:
        log_audit("WORKSPACE_VIOLATION", "system_worker", f"Blocked dangerous path in command: {command}")
        return f"[WORKSPACE SECURITY ERROR] {validation_error}"
        
    # 2. Execute REAL command inside Docker Sandbox
    log_audit("DOCKER_EXECUTION", "system_worker", f"Executing safe command in sandbox: {command}")
    return execute_in_docker(command)