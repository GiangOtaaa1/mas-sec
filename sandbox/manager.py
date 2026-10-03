import os
import subprocess
from config import Config

def execute_in_docker(command: str, username: str = "guest") -> str:
    """
    Execute a shell command safely inside an isolated Docker container.
    Mounts a user-specific workspace to retain files across executions.
    """
    # 1. Prevent Path Traversal 
    base_workspace = os.path.abspath(os.path.join(os.getcwd(), "workspace", "users"))
    user_workspace = os.path.abspath(os.path.join(base_workspace, username))
    
    # SECURITY CHECK: Ensure the user_workspace is a subdirectory of base_workspace
    try:
        if os.path.commonpath([base_workspace, user_workspace]) != base_workspace:
            return "[SECURITY ERROR] Path Traversal attempt detected in username."
    except ValueError:
        return "[SECURITY ERROR] Invalid workspace path."

    # 2. Initialize the user workspace directory if it doesn't exist
    os.makedirs(user_workspace, exist_ok=True)

    try:
        # Define the docker run command with security flags and volume mount
        docker_cmd = [
            "docker", "run", "--rm",       # Auto-remove container when done
            "--network", "none",           # No internet/network access
            "-m", "512m",                  # Limit RAM to 512MB
            "--cpus", "0.5",               # Limit CPU usage
            
            # --- VOLUME MOUNT & WORKDIR ---
            # Note: Mount the user's workspace to /workspace in the container
            "-v", f"{user_workspace}:/workspace",  
            "-w", "/workspace",            # Default working directory
            
            # CLI security flags
            "--cap-drop=ALL",                         # Remove all Linux capabilities
            "--security-opt=no-new-privileges:true",  # Prevent privilege escalation
            # ------------------------------------------------------
            
            Config.DOCKER_IMAGE,           # 'python:3.9-slim' from config.py
            "sh", "-c", command            # Execute the user's command
        ]
        
        # Run the command with a timeout
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=Config.EXECUTION_TIMEOUT
        )
        
        # Format the output
        output = f"--- EXECUTION RESULT ---\n"
        output += f"Command: {command}\n"
        output += f"Workspace: {user_workspace}\n" 
        output += f"STDOUT:\n{result.stdout.strip() if result.stdout else 'None'}\n"
        output += f"STDERR:\n{result.stderr.strip() if result.stderr else 'None'}\n"
        output += f"------------------------"
        
        return output
        
    except subprocess.TimeoutExpired:
        return "[SANDBOX ERROR] Execution timed out. The command took too long."
    except Exception as e:
        return f"[SANDBOX ERROR] Failed to start sandbox: {str(e)}"