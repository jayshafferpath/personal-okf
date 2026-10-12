# scripts/ — verification suite

An eight-layer structural-integrity check for the knowledge base. Single entry point:

```bash
./scripts/verify.sh                              # full suite (manual / CI)
./scripts/verify.sh --changed path/to/doc.md     # fast path (hook)
```

The `--changed` mode runs Layers 1, 2, and 7 against the named file(s); id-uniqueness is still checked globally (cheap, frontmatter-only). Layers 3-6 are skipped. The PostToolUse hook uses this mode for in-turn agent feedback.

For deterministic CI runs, pin "today" so freshness gates are reproducible:

```bash
VERIFY_TODAY=2026-06-22 ./scripts/verify.sh
```

## Layers

| # | Layer | Script | Failure-mode |
|---|---|---|---|
| 0 | Linter regression tests | `test_linters.py` | **Fail** if the suite's own logic regresses. Runs first: every layer below trusts this logic, and these rules fail *silently* when they break — a freshness gate that stops matching still prints OK. |
| 1 | OKF §9 conformance | `okf_conformance.py` | **Fail** on missing/empty `type`, unparseable frontmatter, malformed reserved files, or missing strict-recommended fields (`title`, `description`, `generated`). |
| 2 | Extension-field lint | `lint_extensions.py` | **Fail** on missing required fields (`id`, `type`, `title`, `description`, `owners`, `tags`, `generated`), unknown `type` (vs. `OKF.md` §3 vocab), a `generated`/`verified`/`sources` shape or actor that violates OKF §5.1/§5.2/§7, a footnote label that matches no `sources[].id`, a missing `resource` on a `dashboard`/`pointer`, any retired field (`source_type`, `confidence`, `timestamp`, `last_verified`, `external_url`, `source_url`, `source_last_checked`, `generated_from`, `generated_at`), malformed dates, duplicate `id`. |
| 3 | Link integrity | `check_links.py` | **Warn only** (OKF §11 tolerates broken links). Reports broken targets, escapes above repo root, orphan docs. Exit code stays 0. |
| 4 | Freshness gates | `check_freshness.py` | **Warn** when the latest `verified[].at` is > 180 days old, or the oldest `sources[].last_modified` > 90 days. **Fail** at > 180 days, or when a doc is past its `stale_after`. |
| 5 | Structure parity | `check_structure.py` | **Fail** if any content directory is missing its `index.md` or if reserved files carry disallowed frontmatter. |
| 6 | Index coverage | `check_index_coverage.py` | **Fail** if a direct content document is missing from its directory index, appears more than once, or a direct index link is broken. Supporting `README.md` files are excluded. |
| 7 | `generated.at` freshness on edit | `check_generated_at.py` | **Warn only.** Diffs each file's body against the version at `HEAD`; if the body changed but `generated.at` didn't move, warns with the OKF.md §1 fix (bump `generated.at`; keep `by` as the accountable human for an interactive session, or use an agent actor only for an unattended run). Skips new files (nothing to diff), stamps already dated today (`VERIFY_TODAY` pins "today" here too), and `process:`-generated docs (a deriver rerun is what's supposed to move the stamp). A heuristic that can misfire on a revert/rebase, so it warns rather than blocks. |
| 8 | Agent dry-run | manual | Open a fresh Claude Code session in this repo and try answering a real question about these projects using only what's in this repo. Not part of `verify.sh`. |

## Why not the official Google validator?

PR #125 against [GoogleCloudPlatform/knowledge-catalog](https://github.com/GoogleCloudPlatform/knowledge-catalog/pull/125) is adding `python -m reference_agent validate --bundle . --strict`. Once it's merged and stable, **replace Layer 1** with that command. `okf_conformance.py` mirrors the rules so we don't block on the upstream merge.

## Dependencies

Python 3.10+ and PyYAML. Install from the repo root, like `verify.sh` and the CI workflow:

```bash
python3 -m pip install -r requirements.txt
```

`verify.sh` fails fast with an install hint if PyYAML is missing.

## Authoring helpers

Once Layer 2 trips, the error message names the missing or wrong field. Find the [`../OKF.md`](../OKF.md) §6 example that matches where your content comes from and copy-paste.

## Why the hooks exit 2 on a warn-only Layer 7 message

`hook_verify.sh` (PostToolUse) and `hook_stop_verify.sh` (Stop) don't call `verify.sh` directly — both source `hook_common.sh` and route its output through `report_and_exit`. The reason: Claude Code only surfaces a hook's stdout/stderr to the *agent* when the hook exits 2 (the documented "blocking feedback" contract); exit-0 output goes to a debug log a human might read later, never into the agent's context mid-turn. That makes a warn-only layer whose warning leaves `verify.sh`'s own exit code at 0 invisible to the very agent whose edit triggered it — which defeats the point of a warning meant to be acted on in-turn.

`report_and_exit` borrows exit 2 as a **delivery mechanism** for a Layer 7 warning even when `verify.sh` passed, prefixing the message `ADVISORY ONLY — verify.sh passed, nothing failed or is blocked` so it doesn't read as a blocked edit. A real failure still dumps the full output at exit 2, unchanged. `verify.sh`'s own exit code is untouched either way — CI and a manual run still see Layer 7 as pure warn-only, since neither of those goes through the hook wrappers.

## Not yet built

No deriver scripts exist yet (nothing here is machine-generated from an upstream system). No review-triggered `verified` stamping job exists either — every `verified` entry today is added by hand when a human actually confirms something.