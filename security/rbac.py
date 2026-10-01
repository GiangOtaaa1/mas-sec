# security/rbac.py

def check_permission(role: str, target_agent: str) -> bool:
    """
    Check if a specific role has permission to access the target agent.
    - Guest: Can only use Worker1 (Research)
    - Admin: Can use both Worker1 and Worker2 (Action)
    """
    role = role.lower()
    
    # Define policies
    policies = {
        "guest": ["Worker1"],
        "admin": ["Worker1", "Worker2"]
    }
    
    # Check if target agent is in the allowed list for the role
    allowed_agents = policies.get(role, [])
    return target_agent in allowed_agents