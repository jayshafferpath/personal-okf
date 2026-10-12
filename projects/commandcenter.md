---
type: project
id: commandcenter
title: commandcenter
description: Personal focus dashboard showing Jira tickets, todos, open PRs and live agent sessions, with per-ticket Claude Code dispatch and the Pearl supervisor agent.
owners: [human:jay.shaffer]
tags: [dashboard, jira, agents, tmux]
resource: https://github.com/jayshafferpath/commandcenter
generated:
  by: human:jay.shaffer
  at: 2026-10-12
---

- **Stack:** Node. The API is Fastify (`api/server.js`, port 3789, overridable with `DASHBOARD_PORT`). The UI is React/Vite (`ui/`, port 5173). Tests use Vitest (`tests/`).
- **Run:** `./install.sh` once, then `npm run dev`.
- **Platform:** macOS only. Agents run in `tmux` sessions, and "open terminal" drives iTerm2 through `osascript`.
- **Columns:**
  - Tickets: open, non-Epic issues assigned to you, excluding the `Todo` label.
  - Todos: the [JT project](../pointers/jira-jt.md).
  - PRs: `gh search prs` for author and assignee, across all repos.
  - Sessions: running jobs.
- **Dispatch:** `POST /api/dispatch` resolves the repo from the ticket's `repo:<name>` label to `$DEV_ROOT/<name>`. It prepends the full ticket detail and `/automodel` to the prompt. Only one running job is allowed per ticket (409 otherwise).
- **Pearl:** a persistent supervisor agent in its own tmux session. Personality lives in `SOUL.md`, which is read fresh on every spin-up and can be edited from the Pearl tab.
- **Safety gate:** write actions (dispatch, Pearl, killing a live session) are off unless `DASHBOARD_ALLOW_ACTIONS=true`. When off, the UI only offers copy-to-clipboard.
- **Lifecycle labels:** `api/lib/labels.js` is canonical. See [claude-lifecycle-labels](../concepts/claude-lifecycle-labels.md).
- **Jira access:** see [jira](../integrations/jira.md).

- **Origin:** extracted from `jay-claude-plugins/dashboard/` on 2026-10-09. `SOUL.md` and `commands/automodel.md` were byte-identical at extraction. The two copies now drift independently, so treat commandcenter as the live one. See [jay-claude-plugins](jay-claude-plugins.md).

## Gotchas

- If an older API server still holds port 3789, `npm run dev` keeps serving the UI against the stale server, and new routes return 404. The server prints the `lsof`/`kill` recipe on `EADDRINUSE`.
