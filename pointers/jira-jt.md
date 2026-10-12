---
type: pointer
id: jira-jt
title: JT Jira project ("Jays TODO")
description: Personal todo project on rula.atlassian.net that commandcenter reads and writes.
owners: [human:jay.shaffer]
tags: [jira, todos, commandcenter]
resource: https://rula.atlassian.net/jira/core/projects/JT
external_id: "13429"
generated:
  by: human:jay.shaffer
  at: 2026-10-12
---

Individual issues are not mirrored here because they change daily. Query them live.

- Site: `rula.atlassian.net` (cloudId `7cccece9-ed80-47b1-a46a-6cf64431fd64`)
- Type: team-managed business project, not private
- Issue types: Task, Sub-task
- Workflow: To Do → Done (no review status, so the `review` lifecycle transition is a no-op here)
- Open todos: `project = JT AND labels = "Todo" AND assignee = currentUser() AND statusCategory != Done`

## How commandcenter uses it

The Todos column creates and completes JT issues. It uses `TODO_PROJECT_KEY` (default `JT`), `TODO_ISSUE_TYPE` (default `Task`) and `TODO_LABEL` (default `Todo`). See [commandcenter](../projects/commandcenter.md).

JT is only the todo store. Agent-dispatchable work (`ClaudeWork`) can live in any project assigned to Jay. See [claude-lifecycle-labels](../concepts/claude-lifecycle-labels.md).

Several early issues (JT-2, JT-3, JT-11 to JT-13) are demo or smoke-test todos, not real work.
