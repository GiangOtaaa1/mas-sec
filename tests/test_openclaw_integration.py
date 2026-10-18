import importlib
from types import SimpleNamespace

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage


def test_openclaw_endpoint_uses_authenticated_mas_workflow(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-chars")
    app_module = importlib.import_module("main")
    routes = importlib.import_module("api.routes")
    auth = importlib.import_module("gateway.auth")

    calls = []

    class FakeGraph:
        def __init__(self):
            self.pending = False
            self.approval_granted = False
            self.last_inputs = None
            self.fail_on_resume = False

        def invoke(self, inputs, config):
            if inputs is None:
                if self.fail_on_resume:
                    raise RuntimeError("simulated worker failure")
                self.pending = False
                output = "Approved action completed." if self.approval_granted else "Action rejected."
                return {"messages": [AIMessage(content=output)]}

            calls.append((inputs, config))
            self.last_inputs = inputs
            self.pending = inputs["messages"][0].content == "execute something"
            return {"messages": [AIMessage(content="MAS response")]}

        def get_state(self, config):
            return SimpleNamespace(
                next=["hitl_node"] if self.pending else [],
                values=self.last_inputs or {},
            )

        def update_state(self, config, values):
            self.approval_granted = values["approval_granted"]

    fake_graph = FakeGraph()
    monkeypatch.setattr(routes, "app_graph", fake_graph)
    routes.thread_owners.clear()
    paths = app_module.app.openapi()["paths"]
    expected_routes = {
        "/api/v1/auth/token": {"post"},
        "/api/chat": {"post"},
        "/api/v1/agent/chat": {"post"},
        "/api/v1/agent/status/{thread_id}": {"get"},
        "/api/approvals": {"get"},
        "/api/approve": {"post"},
    }
    assert {path: set(paths[path]) for path in expected_routes} == expected_routes
    route = next(route for route in routes.router.routes if route.path == "/v1/agent/chat")
    assert sum(item.path == "/v1/agent/chat" for item in routes.router.routes) == 1
    gateway_main = importlib.import_module("gateway.main")
    assert not any(item.path == "/api/v1/agent/chat" for item in gateway_main.router.routes)
    assert any(dependency.call is auth.get_current_user for dependency in route.dependant.dependencies)
    monkeypatch.setattr(auth, "SECRET_KEY", "test-secret-key-that-is-at-least-32-chars")
    guest_token = auth.create_access_token({"sub": "openclaw-demo", "role": "guest"})
    admin_token = auth.create_access_token({"sub": "admin-demo", "role": "admin"})

    try:
        with TestClient(app_module.app) as client:
            invalid = client.post(
                "/api/v1/agent/chat",
                json={"prompt": "", "thread_id": "openclaw-test"},
                headers={"Authorization": f"Bearer {guest_token}"},
            )
            unauthorized = client.post(
                "/api/v1/agent/chat",
                json={"prompt": "Summarize this safely", "thread_id": "openclaw-test"},
            )
            response = client.post(
                "/api/v1/agent/chat",
                json={"prompt": "Summarize this safely", "thread_id": "openclaw-test"},
                headers={"Authorization": f"Bearer {guest_token}"},
            )
            waiting = client.post(
                "/api/v1/agent/chat",
                json={"prompt": "execute something", "thread_id": "openclaw-test"},
                headers={"Authorization": f"Bearer {guest_token}"},
            )
            duplicate = client.post(
                "/api/v1/agent/chat",
                json={"prompt": "execute something again", "thread_id": "openclaw-test"},
                headers={"Authorization": f"Bearer {guest_token}"},
            )
            guest_approval = client.post(
                "/api/approve",
                json={"thread_id": "openclaw-test", "is_approved": True},
                headers={"Authorization": f"Bearer {guest_token}"},
            )
            admin_headers = {"Authorization": f"Bearer {admin_token}"}
            guest_headers = {"Authorization": f"Bearer {guest_token}"}
            admin_pending = client.get("/api/approvals", headers=admin_headers)
            guest_status = client.get(
                "/api/v1/agent/status/openclaw-test",
                headers=guest_headers,
            )
            admin_status = client.get(
                "/api/v1/agent/status/openclaw-test",
                headers=admin_headers,
            )
            admin_approval = client.post(
                "/api/approve",
                json={"thread_id": "openclaw-test", "is_approved": True},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert invalid.status_code == 422
        assert unauthorized.status_code == 401
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.json() == {"response": "MAS response", "status": "COMPLETED"}
        assert waiting.status_code == 200
        assert waiting.json()["status"] == "WAITING_FOR_APPROVAL"
        assert duplicate.status_code == 409
        assert guest_approval.status_code == 403
        assert admin_pending.status_code == 200
        assert admin_pending.json() == [
            {
                "thread_id": "openclaw-test",
                "username": "openclaw-demo",
                "request": "execute something",
            }
        ]
        assert guest_status.status_code == 200
        assert guest_status.json()["status"] == "WAITING_FOR_APPROVAL"
        assert admin_status.status_code == 403
        assert admin_approval.status_code == 200
        assert admin_approval.json()["thread_id"] == "openclaw-test"
        assert admin_approval.json()["status"] == "COMPLETED"
        assert "Approved action completed." in admin_approval.json()["response"]
        with TestClient(app_module.app) as client:
            completed_status = client.get(
                "/api/v1/agent/status/openclaw-test",
                headers=guest_headers,
            )
        assert completed_status.status_code == 200
        assert completed_status.json() == {
            "thread_id": "openclaw-test",
            "response": "[HỆ THỐNG] Đã phê duyệt lệnh thành công!\nKết quả:\nApproved action completed.",
            "status": "COMPLETED",
        }
        assert calls[0][0]["messages"][0].content == "Summarize this safely"
        assert calls[0][0]["user_role"] == "guest"
        assert calls[0][1]["configurable"]["thread_id"] == "openclaw-test"
        assert calls[1][0]["messages"][0].content == "execute something"
        assert routes.pending_approvals.get("openclaw-test") is None

        with TestClient(app_module.app) as client:
            rejected_waiting = client.post(
                "/api/v1/agent/chat",
                json={"prompt": "execute something", "thread_id": "openclaw-reject"},
                headers={"Authorization": f"Bearer {guest_token}"},
            )
            rejected = client.post(
                "/api/approve",
                json={"thread_id": "openclaw-reject", "is_approved": False},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert rejected_waiting.json()["status"] == "WAITING_FOR_APPROVAL"
        assert rejected.status_code == 200
        assert rejected.json()["response"] == "[HỆ THỐNG] Đã từ chối lệnh.\nAction rejected."

        with TestClient(app_module.app) as client:
            failure_waiting = client.post(
                "/api/v1/agent/chat",
                json={"prompt": "execute something", "thread_id": "openclaw-failure"},
                headers={"Authorization": f"Bearer {guest_token}"},
            )
            fake_graph.fail_on_resume = True
            failed_approval = client.post(
                "/api/approve",
                json={"thread_id": "openclaw-failure", "is_approved": True},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            failed_status = client.get(
                "/api/v1/agent/status/openclaw-failure",
                headers={"Authorization": f"Bearer {guest_token}"},
            )
            fake_graph.fail_on_resume = False
        assert failure_waiting.json()["status"] == "WAITING_FOR_APPROVAL"
        assert failed_approval.status_code == 500
        assert failed_status.status_code == 200
        assert failed_status.json()["status"] == "FAILED"
        assert "inspect the server logs" in failed_status.json()["response"]
    finally:
        routes.thread_owners.pop("openclaw-test", None)
        routes.thread_owners.pop("openclaw-reject", None)
        routes.pending_approvals.pop("openclaw-test", None)
        routes.pending_approvals.pop("openclaw-reject", None)
        routes.completed_results.pop("openclaw-test", None)
        routes.completed_results.pop("openclaw-reject", None)
        routes.thread_owners.pop("openclaw-failure", None)
        routes.pending_approvals.pop("openclaw-failure", None)
        routes.completed_results.pop("openclaw-failure", None)
