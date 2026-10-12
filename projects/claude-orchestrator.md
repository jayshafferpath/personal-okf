---
type: project
id: claude-orchestrator
title: claude-orchestrator
description: WebSocket web UI that launches jay-claude-plugins queue skills, streams their logs, and shows a Kanban board of ClaudeWork tickets.
owners: [human:jay.shaffer]
tags: [dashboard, agents, jira, dormant]
status: deprecated
resource: https://github.com/jayshafferpath/claude-orchestrator
generated:
  by: human:jay.shaffer
  at: 2026-10-12
---

This is the predecessor of [commandcenter](commandcenter.md). The last commit was on 2026-03-24, and there are only two commits.

- **Stack:** Node ESM, Express 4, ws, node-pty. A postinstall step chmods the darwin-arm64 spawn-helper.
- **Run:** `npm install` then `npm run dev`. It serves HTTP and WebSocket together on port 3100. Tests: `npm test` (`node --test`).
- **External:** Jira REST (`JIRA_HOST`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_POLL_INTERVAL`, `JIRA_PROTOCOL`). It spawns the Claude CLI using `CLAUDE_BIN`, `WORK_DIR` and `PORT`.

## Gotchas

- The skill names it launches (`/jay-claude-queue`, `/jay-queue-plan`, …) predate the March rename sweep in [jay-claude-plugins](jay-claude-plugins.md) and may no longer exist.
- The README links `github.com/jayshaffer/jay-claude-plugins`, which is the wrong owner.
