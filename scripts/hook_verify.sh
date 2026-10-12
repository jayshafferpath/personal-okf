#!/usr/bin/env bash
# PostToolUse hook wrapper.
#
# Claude Code invokes this after a Write/Edit tool call. The tool-call
# payload arrives on stdin as JSON. We:
#   1. Extract the edited file path.
#   2. Early-exit 0 if it's not a markdown file inside this repo.
#   3. Otherwise run scripts/verify.sh --changed on that one file
#      (fast path: conformance + extension lint with global id check,
#      plus the generated.at freshness warning; skips index coverage /
#      freshness / structure / link layers).
#   4. Exit 2 on verifier failure so Claude Code surfaces stderr to the
#      agent as blocking feedback (per the PostToolUse contract). Also
#      exit 2, advisory-only, if verify.sh passed but printed a Layer 7
#      warning — see hook_common.sh for why exit 0 output never reaches
#      the agent.
#
# The repo root is wherever this script lives' parent. We resolve it
# explicitly so the hook works regardless of the caller's cwd.

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/hook_common.sh"

# Read tool-call JSON from stdin (best-effort; if absent, fall back to
# running verify.sh unconditionally — safer than skipping silently).
payload="$(cat)"

# Extract tool_input.file_path with a tiny Python one-liner. Falls back
# to empty string if missing or unparseable.
file_path="$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    sys.exit(0)
tool_input = data.get("tool_input") or {}
print(tool_input.get("file_path") or "")
' 2>/dev/null || true)"

# Early-exit: not a markdown file under the repo root.
case "$file_path" in
  "" )
    # No path discoverable; run verify defensively.
    ;;
  *.md )
    # Only run if the path is under our repo root.
    case "$file_path" in
      "$ROOT"/* ) ;;
      * ) exit 0 ;;
    esac
    ;;
  * )
    exit 0
    ;;
esac

if [[ -z "$file_path" ]]; then
  # No discoverable path; run the full suite defensively.
  out="$(cd "$ROOT" && ./scripts/verify.sh 2>&1)"
  report_and_exit "$out" "$?"
fi

out="$(cd "$ROOT" && ./scripts/verify.sh --changed "$file_path" 2>&1)"
report_and_exit "$out" "$?"
