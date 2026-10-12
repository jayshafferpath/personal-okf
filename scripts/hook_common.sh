# Shared helper for the PostToolUse/Stop hook wrappers (hook_verify.sh,
# hook_stop_verify.sh). Sourced, not executed directly — no shebang.
#
# Claude Code only surfaces a hook's stdout/stderr to the *agent* when the
# hook exits 2 ("blocking feedback", per the hooks contract). Exit-0 output
# goes to a debug log a human might read later, but the agent mid-session
# never sees it. That makes a warn-only layer whose warning leaves
# verify.sh's own exit code at 0 — e.g. Layer 7, generated.at freshness —
# invisible to the very agent whose edit triggered it, which defeats the
# point of a warning meant to be acted on in-turn.
#
# report_and_exit takes verify.sh's combined stdout+stderr and its exit
# code, and never returns:
#   - real failure (nonzero exit): dumps the full output, exit 2. Same
#     behavior as before this file existed.
#   - success (exit 0) but the output carries a Layer 7 warning: dumps
#     just those lines, prefixed unmistakably as advisory-only — verify.sh
#     passed, nothing is blocked — then exit 2 so the agent actually sees
#     them. Exit 2 here is a delivery mechanism, not a failure signal.
#   - success with no such warning: exit 0, silent.
#
# Extend the grep pattern here if a future warn-only layer needs the same
# treatment; today only Layer 7 (check_generated_at.py) opts in.

report_and_exit() {
  local output="$1"
  local status="$2"

  if [[ "$status" -ne 0 ]]; then
    printf '%s\n' "$output" >&2
    exit 2
  fi

  local warnings
  warnings="$(grep '? generated.at:' <<<"$output" || true)"
  if [[ -n "$warnings" ]]; then
    {
      echo "ADVISORY ONLY — verify.sh passed, nothing failed or is blocked:"
      echo
      printf '%s\n' "$warnings"
    } >&2
    exit 2
  fi

  exit 0
}
