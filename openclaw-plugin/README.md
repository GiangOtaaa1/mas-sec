# MAS Security OpenClaw tool

This native OpenClaw tool submits prompts to the MAS API using the configured
guest identity. It does not execute commands; MAS remains responsible for
moderation, role checks, sandboxing, and human approval.

When MAS pauses a request for approval, `mas_chat` waits for up to one minute
while the admin UI lists the exact pending thread ID. If the admin approves or
rejects in time, the tool returns the resumed workflow result to the OpenClaw
conversation. Otherwise, use `mas_approval_status` with the same thread ID
after the admin decides; never resubmit the original command.

See [`../OPENCLAW.md`](../OPENCLAW.md) for environment setup and installation
instructions.

## Build and test

```bash
npm install
npm run plugin:build
npm run plugin:validate
npm test
```

OpenClaw's plugin SDK is experimental. This package is pinned to the OpenClaw
version used to build and validate it; test again when upgrading the Gateway.
