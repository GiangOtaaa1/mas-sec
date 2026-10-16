# policy.py
import os

class SecurityPolicy:
    def __init__(self, base_workspace_dir: str):
        self.base_workspace = os.path.abspath(base_workspace_dir)

    def validate_path_access(self, requested_path: str) -> bool:
        """
        Workspace Policy: Prevent Path Traversal (../../)
        Ensure the requested path is within the base_workspace.
        """
        abs_requested_path = os.path.abspath(requested_path)
        common = os.path.commonpath([self.base_workspace, abs_requested_path])
        return common == self.base_workspace

    def check_abac_permission(self, role: str, action: str, resource_sensitivity: str) -> bool:
        """
        ABAC Policy: Control access based on context (Role + Action + Sensitivity).
        """

        is_allowed = False

        if role == "admin":
            is_allowed = True
        elif role == "guest":
            if action in ["read", "search"] and resource_sensitivity == "low":
                is_allowed = True
            elif action in ["write", "delete", "execute"]:
                is_allowed = False

        return is_allowed

    def requires_hitl(self, role: str, action_type: str) -> bool:
        """
        HITL Policy: Decide whether the task requires human approval.
        """
        high_risk_actions = ["system_exec", "file_delete", "network_request", "permission_change"]
        if action_type in high_risk_actions:
            return True
        return False