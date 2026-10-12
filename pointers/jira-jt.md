---
type: pointer
id: jira-jt
title: JT Jira project ("Jays TODO")
description: Jay's personal Jira project on rula.atlassian.net. It holds todos and the tickets for jayshafferpath work outside the pathccm org; commandcenter reads and writes it.
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

## What else lives here

JT also holds the tickets for jayshafferpath projects and experiments outside the pathccm org. No label or component separates them from todos yet. Anything carrying the `Todo` label appears in the todo query and the Todos column, whatever it is. Agent-dispatchable work (`ClaudeWork`) can be in JT or in any other project assigned to Jay. See [claude-lifecycle-labels](../concepts/claude-lifecycle-labels.md).

Several early issues (JT-2, JT-3, JT-11 to JT-13) are demo or smoke-test todos, not real work.
