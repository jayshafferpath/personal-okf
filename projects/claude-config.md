---
type: project
id: claude-config
title: claude-config
description: Global Claude Code configuration plus export and migrate scripts for moving to a new Mac.
owners: [human:jay.shaffer]
tags: [claude-code, dotfiles, mac-migration]
resource: https://github.com/jayshafferpath/claude-config
generated:
  by: human:jay.shaffer
  at: 2026-10-12
---

- **Contents:** `CLAUDE.md`, `settings.json`, `mcp.json` (empty), `statusline-command.sh`, a macOS notification hook in `hooks/branch.sh`, `commands/`, and a `Brewfile`.
- **Scripts:**
  - `./install.sh` places the Claude config into `~/.claude`. Settings paths assume the same username.
  - `./export.sh` runs on the old Mac and writes `~/mac-migration.tar.gz`. The tarball contains secrets (SSH, GPG, AWS).
  - `./migrate-mac.sh` runs on the new Mac and is idempotent: brew, oh-my-zsh/p10k, asdf, PATH fixup.
- **Relationship:** `commands/` holds older standalone copies of [jay-claude-plugins](jay-claude-plugins.md) commands. The symlinks that jay-claude-plugins installs supersede them.

## Gotchas

- `~/dev/claude-config-main` is not a separate project. It is an unpacked ZIP of an early claude-config state with no `.git`, and it contains a `mac-migration.tar.gz`.
