import { Type } from "typebox";
import { defineToolPlugin } from "openclaw/plugin-sdk/tool-plugin";

type JsonObject = Record<string, unknown>;
const APPROVAL_WAIT_MS = 60_000;
const APPROVAL_POLL_INTERVAL_MS = 2_000;

function isJsonObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getMasBaseUrl(env: Record<string, string | undefined>): URL {
  const baseUrl = new URL(env.MAS_API_BASE_URL ?? "http://127.0.0.1:8000");
  const isLoopback = ["localhost", "127.0.0.1", "[::1]"].includes(baseUrl.hostname);

  if (baseUrl.protocol !== "https:" && !(baseUrl.protocol === "http:" && isLoopback)) {
    throw new Error("MAS_API_BASE_URL must use HTTPS unless it points to loopback.");
  }
  if (baseUrl.username || baseUrl.password || baseUrl.search || baseUrl.hash) {
    throw new Error("MAS_API_BASE_URL must not contain credentials, a query, or a fragment.");
  }

  return baseUrl;
}

async function readJson(response: Response, operation: string): Promise<JsonObject> {
  if (!response.ok) {
    throw new Error(`MAS ${operation} failed with HTTP ${response.status}.`);
  }

  let value: unknown;
  try {
    value = await response.json();
  } catch {
    throw new Error(`MAS ${operation} returned invalid JSON.`);
  }
  if (!isJsonObject(value)) {
    throw new Error(`MAS ${operation} returned an invalid response.`);
  }
  return value;
}

async function readApprovalStatus(
  baseUrl: URL,
  token: string,
  threadId: string,
  fetchImpl: typeof fetch,
): Promise<{ response: string; status: string; thread_id: string }> {
  const statusResponse = await fetchImpl(
    new URL(`/api/v1/agent/status/${encodeURIComponent(threadId)}`, baseUrl),
    {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(15_000),
    },
  );
  const status = await readJson(statusResponse, "approval status");
  if (
    typeof status.response !== "string" ||
    typeof status.status !== "string" ||
    !["WAITING_FOR_APPROVAL", "COMPLETED", "FAILED"].includes(status.status) ||
    status.thread_id !== threadId
  ) {
    throw new Error("MAS approval status did not match the requested thread.");
  }
  return {
    response: status.response,
    status: status.status,
    thread_id: threadId,
  };
}

export async function getMasApprovalStatus(
  threadId: string,
  env: Record<string, string | undefined> = process.env,
  fetchImpl: typeof fetch = fetch,
) {
  const baseUrl = getMasBaseUrl(env);
  const username = env.MAS_API_USERNAME;
  const password = env.MAS_API_PASSWORD;
  if (!username || !password) {
    throw new Error("Set MAS_API_USERNAME and MAS_API_PASSWORD for the OpenClaw Gateway.");
  }

  const loginResponse = await fetchImpl(new URL("/api/v1/auth/token", baseUrl), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
    signal: AbortSignal.timeout(15_000),
  });
  const login = await readJson(loginResponse, "authentication");
  if (typeof login.access_token !== "string" || !login.access_token) {
    throw new Error("MAS authentication response did not include an access token.");
  }
  return readApprovalStatus(baseUrl, login.access_token, threadId, fetchImpl);
}

export async function sendMasChat(
  prompt: string,
  threadId: string,
  env: Record<string, string | undefined> = process.env,
  fetchImpl: typeof fetch = fetch,
) {
  const baseUrl = getMasBaseUrl(env);
  const username = env.MAS_API_USERNAME;
  const password = env.MAS_API_PASSWORD;
  if (!username || !password) {
    throw new Error("Set MAS_API_USERNAME and MAS_API_PASSWORD for the OpenClaw Gateway.");
  }

  const loginResponse = await fetchImpl(new URL("/api/v1/auth/token", baseUrl), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
    signal: AbortSignal.timeout(15_000),
  });
  const login = await readJson(loginResponse, "authentication");
  if (typeof login.access_token !== "string" || !login.access_token) {
    throw new Error("MAS authentication response did not include an access token.");
  }

  const chatResponse = await fetchImpl(new URL("/api/v1/agent/chat", baseUrl), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${login.access_token}`,
    },
    body: JSON.stringify({ prompt, thread_id: threadId }),
    signal: AbortSignal.timeout(15_000),
  });
  const chat = await readJson(chatResponse, "chat");
  if (typeof chat.response !== "string" || typeof chat.status !== "string") {
    throw new Error("MAS chat response did not include response and status fields.");
  }

  const result = {
    response: chat.response,
    status: chat.status,
    thread_id: threadId,
  };
  if (result.status !== "WAITING_FOR_APPROVAL") {
    return result;
  }

  const deadline = Date.now() + APPROVAL_WAIT_MS;
  while (Date.now() < deadline) {
    const status = await readApprovalStatus(
      baseUrl,
      login.access_token,
      threadId,
      fetchImpl,
    );
    if (status.status !== "WAITING_FOR_APPROVAL") {
      return status;
    }
    await new Promise((resolve) => setTimeout(resolve, APPROVAL_POLL_INTERVAL_MS));
  }
  return result;
}

export default defineToolPlugin({
  id: "mas-security",
  name: "MAS Security",
  description: "Send requests through the authenticated MAS security workflow.",
  tools: (tool) => [
    tool({
      name: "mas_chat",
      label: "MAS Security Chat",
      description:
        "Submit a user request to the MAS API. MAS applies moderation, role checks, and approval rules. If approval is required, wait up to one minute for the admin decision and return the completed result when available. If it is still pending, do not resubmit the request; use mas_approval_status with the same thread_id after the admin decides.",
      parameters: Type.Object({
        prompt: Type.String({
          minLength: 1,
          maxLength: 10000,
          description: "The user's request.",
        }),
        thread_id: Type.String({
          minLength: 1,
          maxLength: 128,
          description: "Stable unique ID for this conversation, reused for approval continuations.",
        }),
      }),
      execute: async ({ prompt, thread_id }) => sendMasChat(prompt, thread_id),
    }),
    tool({
      name: "mas_approval_status",
      label: "MAS Approval Status",
      description:
        "Retrieve the result for an existing MAS thread after an administrator approves or rejects it. Do not resubmit the original request. Use the same thread_id returned by mas_chat.",
      parameters: Type.Object({
        thread_id: Type.String({
          minLength: 1,
          maxLength: 128,
          description: "The exact thread_id returned by mas_chat.",
        }),
      }),
      execute: async ({ thread_id }) => getMasApprovalStatus(thread_id),
    }),
  ],
});
