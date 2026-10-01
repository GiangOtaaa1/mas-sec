# security/workspace.py
import os
from config import Config

def validate_command_paths(command: str) -> str | None:
    """
    Scan the command for dangerous path accesses.
    Returns an error message if a violation is found, otherwise returns None.
    """
    # 1. Define dangerous traversal patterns
    dangerous_patterns = [
        "../", 
        "/etc/", 
        "~/", 
        ".ssh",
        "\\..\\" # Windows style traversal
    ]
    
    command_lower = command.lower()
    
    # 2. Fast string check
    for pattern in dangerous_patterns:
        if pattern in command_lower:
            return f"Path Traversal / Unauthorized access detected: '{pattern}' is forbidden."
            
    # 3. (Optional for later) We can also enforce that operations only happen 
    # inside Config.WORKSPACE_BASE_DIR, but string checking is solid for this phase.
    
    return None