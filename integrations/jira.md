---
type: integration
id: jira
title: Jira Cloud
description: Jira as Jay's todo backend and tracker for work outside the pathccm org, and how the personal projects reach it over REST and MCP.
owners: [human:jay.shaffer]
tags: [jira, atlassian, mcp, todos]
generated:
  by: human:jay.shaffer
  at: 2026-10-12
---

## What it's for

Jira is Jay's personal work tracker, not only a team ticketing system.

- **Todo backend:** personal todos are Jira issues in [JT](../pointers/jira-jt.md). commandcenter's Todos column is a front end over them, and there is no separate todo store.
- **Tracker for work outside pathccm:** side projects and experiments under jayshafferpath (see [projects](../projects/index.md)) are tracked in Jira as well, even though their code doesn't live in the pathccm org. Their tickets are what commandcenter's agents pick up and work.

## Access paths

There are two paths, and they authenticate separately.

- **REST:** commandcenter's API server uses `api/lib/jira.js` with basic auth from `JIRA_EMAIL`/`JIRA_API_TOKEN`/`JIRA_DOMAIN`. The `ATLASSIAN_*` names are accepted as aliases. It searches, edits, labels, transitions and creates issues.
- **MCP:** dispatched agents and Pearl use the Atlassian MCP at `https://mcp.atlassian.com/v1/mcp`. commandcenter's `install.sh` registers it with Claude Code if it is missing.

## Gotchas

- In JQL, `labels != "X"` silently drops every issue with no labels. Write `(labels is EMPTY OR labels != "X")` instead.
- Status transitions are matched by name, case-insensitively, and the first match wins. A project without a review status (like [JT](../pointers/jira-jt.md)) skips the review step without failing.
