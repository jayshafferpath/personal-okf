"""Layer 7: generated.at freshness on edit (warn-only).

OKF.md §1: `generated.at` records "when the content last **meaningfully**
changed" (OKF §5.2). Nothing else in the suite checks that it actually moved
when the body did — Layers 1/2 only validate that `generated` is *shaped*
correctly, not that it is *current*. A body edit landing next to a stale
`generated.at` is invisible to every other layer.

This layer diffs each candidate file's frontmatter against the version at
HEAD. If the body changed but `generated.at` did not, warn — worded so an
agent reading the output knows exactly what to do (bump `generated.at`; keep
`by` if this was an interactive, human-steered session, per OKF.md §1).

Warn-only, like Layer 3 (link integrity): a frontmatter/git-history heuristic
can misfire (e.g. a revert, a rebase), so it should surface for a reader to
judge rather than block the commit. Always exits 0.

Scope: only meaningful against a working tree with git history, and only
useful for files that already existed at HEAD (a new file has nothing to
diff against — it was authored with today's timestamp in the same edit, by
construction). Skips `process:`-generated docs: a deriver rerun is what's
supposed to move `generated.at`, not the human/agent editing it by hand.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

from okf_frontmatter import (
    FrontmatterError,
    coerce_date_str,
    is_excluded_path,
    iter_markdown_files,
    parse_frontmatter_text,
    read_frontmatter,
)


def _git(root: Path, *args: str) -> str | None:
    """Run a git command from `root`; return stdout, or None on any failure.

    None covers "not a git repo", "no HEAD" (fresh repo), and "path doesn't
    exist at HEAD" (new file) uniformly — this layer treats all three as
    nothing-to-compare-against, not an error.
    """
    try:
        r = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout


def _generated_at(fm: dict | None) -> str | None:
    """The raw `generated.at` value, normalised to an ISO 8601 string.

    PyYAML resolves an unquoted timestamp to `datetime`/`date`; `str()` on
    those renders `2026-08-13 10:00:00+00:00` (space, `+00:00`) rather than
    the `T...Z` form the frontmatter actually uses, which would make the
    warning's quoted value confusing to copy back in. `coerce_date_str`
    keeps it in the written form for a plain string, and ISO 8601 with `T`
    for the parsed types — good enough to recognise, even if not
    byte-identical to a `Z`-suffixed source.
    """
    gen = fm.get("generated") if fm else None
    at = gen.get("at") if isinstance(gen, dict) else None
    if at is None:
        return None
    return coerce_date_str(at) or str(at)


def _is_process_generated(fm: dict | None) -> bool:
    gen = fm.get("generated") if fm else None
    by = gen.get("by") if isinstance(gen, dict) else None
    return isinstance(by, str) and by.startswith("process:")


def _is_dated(stamp: str, today: date) -> bool:
    return stamp[:10] == today.isoformat()


def check_file(path: Path, root: Path, today: date | None = None) -> str | None:
    """Return a warning string for this file, or None if nothing to flag."""
    today = today or date.today()
    rel = path.relative_to(root)

    head_text = _git(root, "show", f"HEAD:{rel.as_posix()}")
    if head_text is None:
        # No committed version to diff against: not tracked, new, or no git.
        return None

    try:
        head_fm, head_body = parse_frontmatter_text(head_text, path)
    except FrontmatterError:
        # HEAD's frontmatter doesn't parse (e.g. mid-migration history); not
        # this layer's problem to diagnose.
        return None
    if head_fm is None:
        return None

    try:
        now_fm, now_body = read_frontmatter(path)
    except FrontmatterError:
        return None
    if now_fm is None:
        return None

    if _is_process_generated(now_fm):
        return None

    if head_body == now_body:
        # Frontmatter-only edit (or no edit at all) — nothing for the
        # content-freshness stamp to react to.
        return None

    before = _generated_at(head_fm)
    after = _generated_at(now_fm)
    if before is None or after is None:
        # Malformed/missing `generated.at` is Layer 1/2's job to fail on.
        return None

    # A stamp already dated today is current. Without this, a same-day re-edit
    # of a bare-date stamp has no fix and the Stop hook loops on the warning.
    if before == after and not _is_dated(after, today):
        return (
            f"{rel}: body changed but generated.at is still {after!r} — "
            f"bump generated.at (OKF.md §1: it records when the content last "
            f"meaningfully changed). Keep generated.by as the accountable "
            f"human if this was an interactive session they steered; use a "
            f"<producer>/<version> actor only for an unattended agent run."
        )
    return None


def check(root: Path, today: date, only: list[Path] | None = None) -> int:
    if _git(root, "rev-parse", "--is-inside-work-tree") is None:
        print("generated.at freshness (warn-only): skipped (not a git repo)")
        return 0

    paths = only if only is not None else iter_markdown_files(root)
    warnings: list[str] = []
    for path in paths:
        w = check_file(path, root, today)
        if w is not None:
            warnings.append(w)

    print(f"generated.at freshness (warn-only): {len(warnings)} stale")
    for w in warnings:
        print(f"  ? generated.at: {w}")
    return 0


def _resolve_targets(root: Path, changed: list[str]) -> list[Path]:
    out: list[Path] = []
    for c in changed:
        p = Path(c).resolve()
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        if is_excluded_path(rel):
            continue
        if p.suffix == ".md" and p.exists():
            out.append(p)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--changed", nargs="*", default=None,
                    help="check only these paths (still relative to root)")
    ap.add_argument("--today", help="reference date YYYY-MM-DD (default: system today)")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    today = date.fromisoformat(args.today) if args.today else date.today()
    only = _resolve_targets(root, args.changed) if args.changed is not None else None
    sys.exit(check(root, today, only=only))
