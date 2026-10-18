# OpenClaw to MAS demo integration

This is a native OpenClaw tool plugin that forwards a request through the MAS
API. OpenClaw is the chat/agent gateway; LangGraph still selects the Worker,
and MAS remains responsible for authentication, moderation, RBAC, sandboxing,
and human approval. The plugin does not execute shell commands.

## Build and validate the plugin

Requirements: Node 26 (or a supported OpenClaw Node version), npm, and the
OpenClaw version pinned in `openclaw-plugin/package.json`.

```bash
cd openclaw-plugin
npm install
npm run plugin:build
npm run plugin:validate
npm test
```

Install and enable it in the local OpenClaw Gateway:

```bash
openclaw plugins install --link ./openclaw-plugin
openclaw plugins inspect mas-security --runtime --json
```

Installing/enabling a plugin changes the local OpenClaw Gateway configuration.
Review the plugin source before enabling it.

Restricted OpenClaw profiles such as `coding` can exclude plugin tools even
when the plugin is loaded. Keep the profile restricted and add only the MAS
tool to its explicit allowlist, preserving any existing entries:

```bash
openclaw config get tools.profile
openclaw config get tools.alsoAllow
openclaw config patch --stdin <<'JSON'
{tools: {alsoAllow: ["group:web", "mas_chat", "mas_approval_status"]}}
JSON
openclaw config validate
```

The example retains this demo configuration's existing `group:web` allowance.
If your `tools.alsoAllow` contains other entries, include them in the patch
rather than replacing them. Do not change to the unrestricted `full` profile
just to expose this tool.

For a more reliable demo, use a dedicated agent with only the MAS tool instead
of the default `main` agent, whose broader tool set can distract smaller local
models:

```bash
openclaw agents add mas-chat \
  --workspace ~/.openclaw/workspace/mas-chat \
  --agent-dir ~/.openclaw/agents/mas-chat/agent \
  --model ollama/qwen2.5:7b \
  --non-interactive
openclaw config get agents.list
```

Find the array index `N` of the entry whose `id` is `mas-chat`, then restrict
that entry (replace `N` with the index you found):

```bash
openclaw config set 'agents.list[N].tools.profile' minimal
openclaw config set 'agents.list[N].tools.allow' '["mas_chat", "mas_approval_status"]' --strict-json
openclaw config validate
openclaw agent --agent mas-chat \
  --session-key agent:mas-chat:demo \
  --message 'Call mas_chat once with my request and return its result.' \
  --thinking off --json
```

This change is scoped to `mas-chat`; it does not replace the default agent's
tool policy. `minimal` plus the per-agent allowlist is intended to keep the
model's available tool set small. Verify the agent run's `toolSummary` names
`mas_chat` before treating it as an OpenClaw-to-MAS tool invocation.

For the `mas-chat` agent workspace, keep an `AGENTS.md` instruction that tells
the agent to forward the actual user request through `mas_chat` once and relay
the MAS response faithfully. If the result is still waiting after the tool's
bounded wait, retain the returned `thread_id`; after the administrator decides,
use `mas_approval_status` with that exact ID rather than resubmitting the
command. Do not instruct this agent to search the web or perform MAS work
itself.

## Configure the MAS connection

Run the MAS API on loopback for a local demonstration:

```bash
cd ~/mas-security
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000
```

After updating this code, restart the existing `main:app` process once so it
loads the new approval-list and result-status endpoints. Do not start a second
process on port 8000 while the old one is still running.

If port 8000 is occupied by `gateway.main:app`, stop that process in the
terminal where it was started, then run the command above from the repository
root. Do not try to work around this by removing authentication or proxying to
the gateway-only app.

Use the repository-root `main:app` entry point. `gateway.main:app` is a
separate gateway-only application: it exposes login but does not mount the
chat or approval router. Starting that app can make login work while
`POST /api/v1/agent/chat` returns 405 because the root static-file mount
receives the unmatched POST.

Expected API routes in `http://127.0.0.1:8000/openapi.json`:

- `POST /api/v1/auth/token`
- `POST /api/chat`
- `POST /api/v1/agent/chat`
- `GET /api/v1/agent/status/{thread_id}`
- `GET /api/approvals` (admin only)
- `POST /api/approve`

Confirm them before testing the OpenClaw agent:

```bash
curl -fsS http://127.0.0.1:8000/openapi.json |
  python -c 'import json,sys; paths=json.load(sys.stdin)["paths"]; print("\n".join(f"{method.upper()} {path}" for path in sorted(paths) for method in sorted(paths[path])))'
```

Authenticate and call the chat endpoint without printing the bearer token:

```bash
set +x
MAS_TOKEN=$(curl -fsS http://127.0.0.1:8000/api/v1/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username":"guest","password":"guest123"}' |
  python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
curl -fsS http://127.0.0.1:8000/api/v1/agent/chat \
  -H "Authorization: Bearer $MAS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Reply with exactly: MAS API works.","thread_id":"openclaw-demo-1"}'
unset MAS_TOKEN
```

Expected login status is `200`; chat should return JSON with `response` and
`status: "COMPLETED"`. Without a token the chat endpoint should return `401`.
An empty prompt or invalid thread ID should return `422`.

The OpenClaw Gateway process needs these environment variables:

- `MAS_API_BASE_URL` (defaults to `http://127.0.0.1:8000`; remote hosts require HTTPS)
- `MAS_API_USERNAME`
- `MAS_API_PASSWORD`

For a one-off local Gateway launched from a shell, export these variables in
that shell before starting OpenClaw. For the systemd user service, put the
values in a separate file readable only by your account (mode `600`) and add
that file as an `EnvironmentFile=` in a systemd user-service drop-in. Do not
put passwords in this repository or in chat transcripts. The sample `guest`
account is hard-coded for demonstration only and must not be used in production.

The plugin logs in to `POST /api/v1/auth/token` for each call and sends the
resulting short-lived token to `POST /api/v1/agent/chat` using the HTTP
Authorization header with the Bearer scheme. The request body is
`{"prompt":"...","thread_id":"..."}`. OpenClaw should reuse a stable unique
`thread_id` for follow-up requests in the same conversation. A
`WAITING_FOR_APPROVAL` means the graph is paused and the administrator must
decide. The admin UI's pending list reads `GET /api/approvals` and displays the
exact thread ID and request; approving/rejecting that entry calls
`POST /api/approve` with the same ID. That endpoint resumes the graph
synchronously and returns the final result to the admin UI. Guest callers
cannot approve.

The OpenClaw tool polls `GET /api/v1/agent/status/{thread_id}` for up to one
minute and returns the final approval/rejection result to the still-running
OpenClaw tool call if the admin decides in that interval. This is polling, not
a server push. If the wait expires, `mas_approval_status` retrieves the result
later using the same thread ID; do not resubmit the original command.
Checkpoint and result state are in memory, so restart the API only after
pending approvals are resolved and use a single API process for this demo.

The guest web chat also polls the same thread after `WAITING_FOR_APPROVAL` and
shows the final output after the admin decides. If approval continuation fails,
the guest sees a `FAILED` status asking the administrator to inspect server
logs; the action is not automatically retried.

Guest requests routed to Worker2 are never executed directly: MAS pauses them
at HITL even when the requested operation appears harmless. Only an admin
approval resumes Worker2, and the worker still executes inside the Docker
sandbox using the guest workspace. Guest requests rejected by moderation or
the guest command restrictions remain blocked.

## Demonstration boundary

The plugin can be built and validated without changing the running OpenClaw
Gateway. A successful plugin validation proves that OpenClaw recognizes the tool. A
direct call to the plugin handler can verify the plugin-to-API contract, but it
does not prove that a chat model invoked the tool through the Gateway. The
dedicated `mas-chat` agent has completed a single `mas_chat` call to MAS in
this environment; that verifies the route, but not repeated reliability or
that MAS will follow arbitrary formatting instructions. A full conversational
demonstration additionally requires observing a successful `mas_chat` tool call
in the agent `toolSummary` and checking the returned MAS response. If the model
provider times out before the tool call, report that as an incomplete
Gateway-to-agent demonstration, not as a plugin/API failure.
