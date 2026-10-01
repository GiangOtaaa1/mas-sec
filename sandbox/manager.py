# sandbox/manager.py
import subprocess
from config import Config

def execute_in_docker(command: str) -> str:
    """
    Execute a shell command safely inside an isolated Docker container.
    The container has no network access and strict resource limits.
    """
    try:
        # Define the docker run command with security flags
        docker_cmd = [
            "docker", "run", "--rm",       # Auto-remove container when done
            "--network", "none",           # No internet/network access
            "-m", "512m",                  # Limit RAM to 512MB
            "--cpus", "0.5",               # Limit CPU usage
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
        output += f"STDOUT:\n{result.stdout.strip() if result.stdout else 'None'}\n"
        output += f"STDERR:\n{result.stderr.strip() if result.stderr else 'None'}\n"
        output += f"------------------------"
        
        return output
        
    except subprocess.TimeoutExpired:
        return "[SANDBOX ERROR] Execution timed out. The command took too long."
    except Exception as e:
        return f"[SANDBOX ERROR] Failed to start sandbox: {str(e)}"