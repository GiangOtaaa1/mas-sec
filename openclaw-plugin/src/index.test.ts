import { describe, expect, it } from "vitest";
import entry from "./index.js";
import { getMasApprovalStatus, sendMasChat } from "./index.js";
import { getToolPluginMetadata } from "openclaw/plugin-sdk/tool-plugin";

describe("mas-security", () => {
  it("declares an MAS chat tool", () => {
    expect(getToolPluginMetadata(entry)?.tools.map((tool) => tool.name)).toEqual([
      "mas_chat",
      "mas_approval_status",
    ]);
  });

  it("waits for approval and returns the result for the same thread", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const fetchMock: typeof fetch = async (input, init) => {
      const url = String(input);
      calls.push({ url, init });
      if (url.endsWith("/api/v1/auth/token")) {
        return Response.json({ access_token: "short-lived-test-token" });
      }
      if (url.endsWith("/api/v1/agent/chat")) {
        return Response.json({
          response: "Waiting for admin approval.",
          status: "WAITING_FOR_APPROVAL",
        });
      }
      return Response.json({
        thread_id: "openclaw-hitl-thread",
        response: "Approved result from sandbox.",
        status: "COMPLETED",
      });
    };

    await expect(
      sendMasChat(
        "Run the requested action",
        "openclaw-hitl-thread",
        {
          MAS_API_BASE_URL: "http://127.0.0.1:8000",
          MAS_API_USERNAME: "guest",
          MAS_API_PASSWORD: "test-password",
        },
        fetchMock,
      ),
    ).resolves.toEqual({
      response: "Approved result from sandbox.",
      status: "COMPLETED",
      thread_id: "openclaw-hitl-thread",
    });
    expect(calls.map((call) => call.url)).toEqual([
      "http://127.0.0.1:8000/api/v1/auth/token",
      "http://127.0.0.1:8000/api/v1/agent/chat",
      "http://127.0.0.1:8000/api/v1/agent/status/openclaw-hitl-thread",
    ]);
  });

  it("can fetch the result later without resubmitting the request", async () => {
    const calls: string[] = [];
    const fetchMock: typeof fetch = async (input) => {
      const url = String(input);
      calls.push(url);
      if (url.endsWith("/api/v1/auth/token")) {
        return Response.json({ access_token: "short-lived-test-token" });
      }
      return Response.json({
        thread_id: "openclaw-later-thread",
        response: "Completed after approval.",
        status: "COMPLETED",
      });
    };
    await expect(
      getMasApprovalStatus(
        "openclaw-later-thread",
        {
          MAS_API_BASE_URL: "http://127.0.0.1:8000",
          MAS_API_USERNAME: "guest",
          MAS_API_PASSWORD: "test-password",
        },
        fetchMock,
      ),
    ).resolves.toEqual({
      thread_id: "openclaw-later-thread",
      response: "Completed after approval.",
      status: "COMPLETED",
    });
    expect(calls).toEqual([
      "http://127.0.0.1:8000/api/v1/auth/token",
      "http://127.0.0.1:8000/api/v1/agent/status/openclaw-later-thread",
    ]);
  });

  it("authenticates and forwards requests to the MAS endpoint", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const fetchMock: typeof fetch = async (input, init) => {
      calls.push({ url: String(input), init });
      if (calls.length === 1) {
        return Response.json({ access_token: "short-lived-test-token" });
      }
      return Response.json({ response: "Request approved for research.", status: "COMPLETED" });
    };

    await expect(
      sendMasChat(
        "Summarize the document",
        "openclaw-demo-thread",
        {
          MAS_API_BASE_URL: "http://127.0.0.1:8000",
          MAS_API_USERNAME: "guest",
          MAS_API_PASSWORD: "test-password",
        },
        fetchMock,
      ),
    ).resolves.toEqual({
      response: "Request approved for research.",
      status: "COMPLETED",
      thread_id: "openclaw-demo-thread",
    });
    expect(calls.map((call) => call.url)).toEqual([
      "http://127.0.0.1:8000/api/v1/auth/token",
      "http://127.0.0.1:8000/api/v1/agent/chat",
    ]);
    expect(calls[1].init?.headers).toMatchObject({
      Authorization: "Bearer short-lived-test-token",
    });
    expect(calls[1].init?.body).toBe(
      JSON.stringify({ prompt: "Summarize the document", thread_id: "openclaw-demo-thread" }),
    );
  });

  it("rejects unencrypted remote MAS endpoints", async () => {
    await expect(
      sendMasChat(
        "Do something",
        "thread",
        {
          MAS_API_BASE_URL: "http://mas.example.test",
          MAS_API_USERNAME: "guest",
          MAS_API_PASSWORD: "test-password",
        },
        fetch,
      ),
    ).rejects.toThrow("must use HTTPS");
  });
});
