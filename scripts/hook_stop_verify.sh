#!/usr/bin/env bash
# Stop hook: runs the full verification suite when Claude Code ends a turn.
#
# Complements the PostToolUse fast path (hook_verify.sh). That hook runs
# only Layers 1-2 and 7 on the edited file; this one runs the whole suite so
# that whatever the fast path skipped (freshness gates, structure parity,
# link-integrity warnings, cross-file effects of deletions) is caught
# before the turn closes.
#
# Skip-when-nothing-changed: Stop fires on every turn, including purely
# conversational ones. If no .md files differ from the last commit, exit
# 0 immediately — no point running ~400ms of checks when the corpus is
# byte-identical.
#
# Exit codes:
#   0 — nothing relevant changed, or full suite passes with no warnings
#       worth surfacing.
#   2 — full suite found a failure-mode violation, OR it passed but
#       printed a Layer 7 (generated.at freshness) warning. Claude Code
#       only surfaces a hook's output to the agent on exit 2 — see
#       hook_common.sh — so the warn-only case borrows the same exit
#       code purely as a delivery mechanism, prefixed advisory-only so
#       it doesn't read as a blocked edit.

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 0
source "$ROOT/scripts/hook_common.sh"

# Discard the Stop event payload on stdin; we don't need it.
cat >/dev/null 2>&1 || true

# If git isn't here for some reason (shouldn't happen in this repo),
# just run the suite — safer than skipping silently.
if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
  changed="$(git status --porcelain -- '*.md' ':(exclude).git' 2>/dev/null || true)"
  if [[ -z "$changed" ]]; then
    exit 0
  fi
fi

out="$(./scripts/verify.sh 2>&1)"
report_and_exit "$out" "$?"
