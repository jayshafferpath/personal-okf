---
type: concept
id: claude-lifecycle-labels
title: Claude lifecycle labels
description: The Jira labels and status transitions that record where an agent is on a ticket.
owners: [human:jay.shaffer]
tags: [jira, agents, commandcenter, conventions]
generated:
  by: human:jay.shaffer
  at: 2026-10-12
sources:
  - id: commandcenter-labels-js
    resource: https://github.com/jayshafferpath/commandcenter/blob/main/api/lib/labels.js
    last_modified: 2026-10-12
---

The canonical list lives in `commandcenter/api/lib/labels.js`. It wins on any disagreement with this page. Command markdown must cite that file and must not re-list the labels.

The design rule is that a state gets a label only when another process needs to see it: a peer agent, a JQL query, or a human handing work back. Anything derivable from git, the PR or the checklist is read from that source instead.

- **Durable:** `ClaudeWork` marks a ticket as agent-dispatchable. It is never removed.
- **Progress:** `ClaudeReady` → `ClaudePlanning` → `ClaudeExecuting` → `ClaudeStackReady`, or `ClaudeFailed`. At most one is active at a time. `/rework` and `/prune` clear them all before applying their own label.
- **In flight:** `ClaudePlanning` and `ClaudeExecuting` mean another agent is mid-run. Queue gating skips these tickets.
- **Container:** `ClaudeStackComplete` goes on the Story or Epic.
- **Complexity:** `complexity:trivial` or `complexity:standard`. A ticket with neither label is treated as standard. Trivial skips the plan, refactor and pr-review steps.
- **Status, not label:** "in review" and "done" are Jira status transitions, not labels. They are best-effort: a workflow with no matching status logs a warning. This replaced the retired `ClaudeNeedsReview` label.
