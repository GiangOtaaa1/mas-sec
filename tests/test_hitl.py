import importlib
from types import SimpleNamespace

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from security.moderator import ModerationResult
from sandbox.manager import execute_in_docker


def test_langgraph_hitl_requires_admin_and_resumes_only_after_decision(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-chars")
    app_module = importlib.import_module("main")
    routes = importlib.import_module("api.routes")
    auth = importlib.import_module("gateway.auth")
    workflow = importlib.import_module("graph.workflow")

    worker_calls = []
    monkeypatch.setattr(
        workflow,
        "moderate_request",
        lambda _prompt: ModerationResult(action="ALLOW", reason="test request"),
    )
    monkeypatch.setattr(
        workflow,
        "get_orchestrator",
        lambda: SimpleNamespace(
            invoke=lambda _inputs: SimpleNamespace(next_agent="Worker2")
        ),
    )

    class SandboxWorker:
        def __init__(self, username):
            self.username = username

        def invoke(self, _inputs):
            worker_calls.append("executed")
            output = execute_in_docker(
                "printf 'HITL_APPROVED_DOCKER_PROOF'",
                username=self.username,
            )
            return {"messages": [AIMessage(content=output)]}

    monkeypatch.setattr(
        workflow,
        "get_worker2",
        lambda *, username: SandboxWorker(username),
    )
    monkeypatch.setattr(routes, "app_graph", workflow.build_graph())
    routes.pending_approvals.clear()
    routes.thread_owners.clear()

    monkeypatch.setattr(auth, "SECRET_KEY", "test-secret-key-that-is-at-least-32-chars")
    admin_token = auth.create_access_token({"sub": "admin-test", "role": "admin"})
    guest_token = auth.create_access_token({"sub": "guest-test", "role": "guest"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    guest_headers = {"Authorization": f"Bearer {guest_token}"}

    approve_thread = "hitl-guest-approve-test"
    reject_thread = "hitl-guest-reject-test"
    try:
        with TestClient(app_module.app) as client:
            waiting = client.post(
                "/api/v1/agent/chat",
                headers=guest_headers,
                json={
                    "prompt": "Use Worker2 to run printf 'HITL_APPROVED_DOCKER_PROOF' in Docker",
                    "thread_id": approve_thread,
                },
            )
            assert waiting.status_code == 200
            assert waiting.json()["status"] == "WAITING_FOR_APPROVAL"
            assert worker_calls == []
            pending = client.get("/api/approvals", headers=admin_headers)
            assert pending.status_code == 200
            assert pending.json() == [
                {
                    "thread_id": approve_thread,
                    "username": "guest-test",
                    "request": "Use Worker2 to run printf 'HITL_APPROVED_DOCKER_PROOF' in Docker",
                }
            ]

            guest_approval = client.post(
                "/api/approve",
                headers=guest_headers,
                json={"thread_id": approve_thread, "is_approved": True},
            )
            assert guest_approval.status_code == 403
            assert worker_calls == []
            owner_status = client.get(
                f"/api/v1/agent/status/{approve_thread}",
                headers=guest_headers,
            )
            admin_status = client.get(
                f"/api/v1/agent/status/{approve_thread}",
                headers=admin_headers,
            )
            assert owner_status.status_code == 200
            assert owner_status.json()["status"] == "WAITING_FOR_APPROVAL"
            assert admin_status.status_code == 403

            approval = client.post(
                "/api/approve",
                headers=admin_headers,
                json={"thread_id": approve_thread, "is_approved": True},
            )
            assert approval.status_code == 200
            assert "HITL_APPROVED_DOCKER_PROOF" in approval.json()["response"]
            assert "SANDBOX ERROR" not in approval.json()["response"]
            assert worker_calls == ["executed"]
            result = client.get(
                f"/api/v1/agent/status/{approve_thread}",
                headers=guest_headers,
            )
            assert result.status_code == 200
            assert result.json()["status"] == "COMPLETED"
            assert "HITL_APPROVED_DOCKER_PROOF" in result.json()["response"]

            waiting = client.post(
                "/api/v1/agent/chat",
                headers=guest_headers,
                json={
                    "prompt": "Use Worker2 to run printf 'HITL_REJECTED_DOCKER_PROOF' in Docker",
                    "thread_id": reject_thread,
                },
            )
            assert waiting.status_code == 200
            assert waiting.json()["status"] == "WAITING_FOR_APPROVAL"
            calls_before_rejection = len(worker_calls)

            rejection = client.post(
                "/api/approve",
                headers=admin_headers,
                json={"thread_id": reject_thread, "is_approved": False},
            )
            assert rejection.status_code == 200
            assert "rejected" in rejection.json()["response"].lower()
            assert len(worker_calls) == calls_before_rejection
    finally:
        routes.pending_approvals.pop(approve_thread, None)
        routes.pending_approvals.pop(reject_thread, None)
        routes.completed_results.pop(approve_thread, None)
        routes.completed_results.pop(reject_thread, None)
        routes.thread_owners.pop(approve_thread, None)
        routes.thread_owners.pop(reject_thread, None)
