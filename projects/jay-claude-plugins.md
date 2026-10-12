---
type: project
id: jay-claude-plugins
title: jay-claude-plugins
description: Claude Code agents, slash commands and Node CLIs that automate Jira tickets, stacked PRs and TDD-to-merge workflows.
owners: [human:jay.shaffer]
tags: [claude-code, agents, jira, stacked-prs]
resource: https://github.com/jayshafferpath/jay-claude-plugins
generated:
  by: human:jay.shaffer
  at: 2026-10-12
---

This is the core of the personal tooling and the most active repo. The other projects either consume it or were split out of it.

- **Contents:**
  - `agents/`: planner, feature-planner, tdd-builder, refactor, condensor, diff-critic, diff-security and others.
  - `commands/`: `/ticket-work`, `/prework`, `/orchestrate`, `/cleanup`, `/groom-stack` and others. Files prefixed `_` are shared fragments, not commands.
  - `cli/bin/`: about 27 Node CLIs (resolve-stack, set-ticket-state, drift-check, sync-opencode, …) with shared code in `cli/lib/`.
  - `dashboard/`: the original copy of [commandcenter](commandcenter.md).
- **Install:** `./install.sh` symlinks `commands/` and `agents/` into `~/.claude/` and writes wrappers into `~/.local/bin/`. That directory must come before `~/.asdf/shims` on PATH.
- **Tests:** Vitest in `cli/tests/` with 90% coverage enforced. CI (`.github/workflows/test.yml`) runs Biome and coverage on PRs.
- **External:** Jira REST and the Atlassian MCP ([jira](../integrations/jira.md)), GitHub via `gh`, and Slack through an optional `SLACK_WEBHOOK_URL`.
- **Lifecycle:** see [claude-lifecycle-labels](../concepts/claude-lifecycle-labels.md). To enqueue a ticket, add both `ClaudeWork` and `ClaudeReady`.

## Gotchas

- Jira, not git, is the source of truth for stack structure.
- Every PR opens as a draft.
- opencode gets generated copies through `sync-opencode`, not symlinks. A shared file would silently give the read-only reviewer agents write access. `sync-opencode --check` exits 2 when the copies are stale.
