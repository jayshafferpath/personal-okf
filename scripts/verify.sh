#!/usr/bin/env bash
# Single entry point for the structural-integrity verification suite.
# Runs all layers; exits non-zero if any failure-mode layer fails.
# Layer 0 tests the linters themselves; layers 3 and 7 are warn-only by
# design (OKF §11 for links; generated.at freshness is a heuristic that can
# misfire on a revert/rebase, so it surfaces for a reader rather than blocks).
#
# Modes:
#   verify.sh                           full suite (manual + CI)
#   verify.sh --changed FILE [FILE...]  fast path: layers 1-2 and 7 on named
#                                       files only (id-uniqueness still
#                                       global). Skips layers 3-6. Used by
#                                       the PostToolUse hook.

set -u
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
SCRIPTS="$ROOT/scripts"
PY="${PYTHON:-python3}"

TODAY="${VERIFY_TODAY:-}"
FRESH_ARGS=("$ROOT")
if [[ -n "$TODAY" ]]; then
  FRESH_ARGS+=("--today" "$TODAY")
fi

# Fail once, clearly, rather than letting all five layers each emit the same
# import error. PyYAML is required for OKF 0.2's nested frontmatter (`generated`
# / `verified` / `sources`).
if ! "$PY" -c "import yaml" >/dev/null 2>&1; then
  cat >&2 <<EOF
verify: PyYAML is not installed for $PY.

  install it with:  $PY -m pip install -r requirements.txt

The verify suite needs a real YAML parser for OKF 0.2's nested \`generated\` /
\`verified\` / \`sources\` mappings.
EOF
  exit 69
fi

run() {
  local label="$1"; shift
  echo "── $label ──"
  if "$@"; then
    return 0
  else
    return 1
  fi
}

status=0

if [[ "${1:-}" == "--changed" ]]; then
  shift
  if [[ $# -eq 0 ]]; then
    echo "verify.sh --changed: no paths given" >&2
    exit 64
  fi
  run "Layer 1: OKF §9 conformance (changed)" \
    "$PY" "$SCRIPTS/okf_conformance.py" "$ROOT" --changed "$@" || status=1
  echo
  run "Layer 2: extension-field lint (changed)" \
    "$PY" "$SCRIPTS/lint_extensions.py" "$ROOT" --changed "$@" || status=1
  echo
  run "Layer 7: generated.at freshness on edit (changed, warn-only)" \
    "$PY" "$SCRIPTS/check_generated_at.py" "$ROOT" --changed "$@"
  echo
  if [[ $status -ne 0 ]]; then
    echo "verify (changed): FAIL"
  else
    echo "verify (changed): OK"
  fi
  exit $status
fi

# Layer 0: the linters' own regression tests. Runs first because every layer
# below trusts this logic — a validator that silently stopped matching would
# leave the whole suite printing OK.
run "Layer 0: linter regression tests" "$PY" "$SCRIPTS/test_linters.py" || status=1
echo
run "Layer 1: OKF §9 conformance" "$PY" "$SCRIPTS/okf_conformance.py" "$ROOT" || status=1
echo
run "Layer 2: extension-field lint" "$PY" "$SCRIPTS/lint_extensions.py" "$ROOT" || status=1
echo
run "Layer 3: link integrity (warn-only)" "$PY" "$SCRIPTS/check_links.py" "$ROOT"
echo
run "Layer 4: freshness" "$PY" "$SCRIPTS/check_freshness.py" "${FRESH_ARGS[@]}" || status=1
echo
run "Layer 5: structure parity" "$PY" "$SCRIPTS/check_structure.py" "$ROOT" || status=1
echo
run "Layer 6: index coverage" "$PY" "$SCRIPTS/check_index_coverage.py" "$ROOT" || status=1
echo
run "Layer 7: generated.at freshness on edit (warn-only)" \
  "$PY" "$SCRIPTS/check_generated_at.py" "$ROOT"
echo

if [[ $status -ne 0 ]]; then
  echo "verify: FAIL"
else
  echo "verify: OK"
fi
exit $status
