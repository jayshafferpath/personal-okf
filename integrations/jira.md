---
type: integration
id: jira
title: Jira Cloud
description: How the personal projects reach Jira. The REST API carries dashboard reads and writes; the Atlassian MCP carries agent sessions.
owners: [human:jay.shaffer]
tags: [jira, atlassian, mcp]
generated:
  by: human:jay.shaffer
  at: 2026-10-12
---

There are two paths, and they authenticate separately.

- **REST:** commandcenter's API server uses `api/lib/jira.js` with basic auth from `JIRA_EMAIL`/`JIRA_API_TOKEN`/`JIRA_DOMAIN`. The `ATLASSIAN_*` names are accepted as aliases. It searches, edits, labels, transitions and creates issues.
- **MCP:** dispatched agents and Pearl use the Atlassian MCP at `https://mcp.atlassian.com/v1/mcp`. commandcenter's `install.sh` registers it with Claude Code if it is missing.

## Gotchas

- In JQL, `labels != "X"` silently drops every issue with no labels. Write `(labels is EMPTY OR labels != "X")` instead.
- Status transitions are matched by name, case-insensitively, and the first match wins. A project without a review status (like [JT](../pointers/jira-jt.md)) skips the review step without failing.
