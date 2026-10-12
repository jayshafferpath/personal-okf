---
type: project
id: proof
title: proof
description: Generates a self-contained HTML walkthrough of a PR, covering decisions and runtime behaviour with a provenance tier on each claim. It explains changes; it does not review them.
owners: [human:jay.shaffer]
tags: [claude-code-plugin, pull-requests, html]
resource: https://github.com/jayshafferpath/proof
generated:
  by: human:jay.shaffer
  at: 2026-10-12
---

- **Stack:** Node 18 or newer with no install step; EJS is vendored in `generator/vendor/`. Bash, `jq`, `gh`. JSON schemas live in `schemas/`.
- **Distribution:**
  - As a Claude Code plugin: `/plugin marketplace add <path>` then `/plugin install proof@proof`. This adds the skills `/proof:decision-log`, `/proof:retrofit-ledger <pr>` and `/proof:retrofit-stack`.
  - As CLIs: `npm install -g <path>` installs `proof`, `proof-retrofit` and `proof-render`.
- **Model step:** Bedrock through the `aws` CLI, falling back to the `opencode` CLI.
- **CI:** `.github/workflows/proof.yml` uses Bedrock via OIDC and upserts a PR comment. Skip it with the `skip-proof` label. It runs `continue-on-error`.
- **Hooks:** `hooks/` holds observe-edit, record-approval and reconcile-stop. They stay inert on main/master/develop and on any branch until `start` has been run.
- **Ledger:** keyed by Jira key and EARS AC id, so it fits the [jay-claude-plugins](jay-claude-plugins.md) workflow. Commit `.proof/ledgers/`; gitignore `.proof/scratch/`.

## Gotchas

- There is no test suite. The safety net is `./build.sh` producing byte-identical output, plus `validate.js`.
- `prototype/*.html` is generated and gitignored. Never edit it by hand; a diff sort control was lost that way once.
- Templates use only `<%-` with the `esc`/`richText` helpers. `<%=` should never appear.
