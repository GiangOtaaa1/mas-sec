# security/audit.py
import logging
import os

# Create log file in the root of the project
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "security_audit.log")

# Configure standard Python logger
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
audit_logger = logging.getLogger("MAS_AUDIT")

def log_audit(event_type: str, user_role: str, details: str):
    """
    Writes a structured audit log to the file and prints it to the console.
    """
    log_msg = f"[{event_type}] [Role: {user_role}] {details}"
    audit_logger.info(log_msg)
    
    # Print to console for easy monitoring during the demo
    print(f"\n---> [AUDIT LOG WRITTEN]: {log_msg}\n")