"""Layer 4: freshness gates.

Encodes the trust-model freshness signals from OKF.md:

- any doc past its `stale_after` (OKF §5.5): fail, on or after that date.
- docs with `sources`: warn if the oldest `sources[].last_modified` is > 90 days;
  fail at > 180 — except for `process:`-generated docs, which warn only (their
  source age is a deriver's concern and no in-repo action can clear it). A doc
  is only as fresh as its stalest input. Checked independently of `stale_after`:
  a future expiry is a claim about the content, not evidence its sources are
  current.
- all docs: warn if the most recent verification is > 180 days old. Recency comes
  from the latest `verified[].at` (OKF §5.2: "'how recently' is the latest
  `at`").

The "today" reference date is sourced from --today YYYY-MM-DD (preferred
for deterministic CI) or the system clock as a fallback.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from okf_frontmatter import (
    FrontmatterError,
    coerce_date_str,
    iter_markdown_files,
    read_frontmatter,
)


RESERVED_NAMES = {"index.md", "log.md"}
EXEMPT_TOPLEVEL_NAMES = {"README.md", "CLAUDE.md", "OKF.md", "MAINTENANCE.md"}


def parse_ymd(value):
    """Coerce a frontmatter date-ish value to a `date`, or None if malformed.

    PyYAML hands back `date` / `datetime` objects for unquoted dates, so this
    normalises through coerce_date_str rather than assuming `str` (which would
    raise TypeError on the slice below).
    """
    s = coerce_date_str(value)
    if s is None:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def days_between(today: date, then: date) -> int:
    return (today - then).days


def oldest_source_date(fm: dict):
    """Oldest `sources[].last_modified`, or None if absent / malformed.

    The *oldest* rather than the newest: a doc curated from several sources is
    only as fresh as its stalest input. Replaces a scalar `source_last_checked`
    (OKF §5.1).
    """
    srcs = fm.get("sources")
    if not isinstance(srcs, list):
        return None
    dates = [
        parse_ymd(e.get("last_modified"))
        for e in srcs
        if isinstance(e, dict)
    ]
    dates = [d for d in dates if d is not None]
    return min(dates) if dates else None


def latest_verified(fm: dict):
    """Most recent `verified[].at`, or None if unverified / malformed.

    OKF §5.2: `verified` is a list of `{by, at}` events and "how recently" is
    the latest `at`; a single verifier MAY be written as a bare mapping, which
    consumers MUST treat as a one-element list. Shape errors are layer 2's job,
    so anything unparseable is simply skipped here.
    """
    ver = fm.get("verified")
    if ver is None:
        return None
    entries = [ver] if isinstance(ver, dict) else ver
    if not isinstance(entries, list):
        return None
    dates = [
        parse_ymd(e.get("at"))
        for e in entries
        if isinstance(e, dict)
    ]
    dates = [d for d in dates if d is not None]
    return max(dates) if dates else None


def check(root: Path, today: date) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    for path in iter_markdown_files(root):
        rel = path.relative_to(root)
        name = path.name
        if name in RESERVED_NAMES:
            continue
        if name in EXEMPT_TOPLEVEL_NAMES and len(rel.parts) == 1:
            continue
        if name == "README.md":
            continue
        try:
            fm, _body = read_frontmatter(path)
        except FrontmatterError:
            continue
        if fm is None:
            continue

        lv = latest_verified(fm)
        if lv is not None and days_between(today, lv) > 180:
            warnings.append(
                f"{rel}: last verified {lv.isoformat()}, "
                f"{days_between(today, lv)} days ago (>180)"
            )

        # OKF §5.5: stale when `today >= stale_after`. Inclusive of the day itself.
        sa = parse_ymd(fm.get("stale_after"))
        if sa is not None and today >= sa:
            errors.append(
                f"{rel}: past its stale_after={sa.isoformat()} "
                f"({days_between(today, sa)} days ago) — refresh or extend it"
            )

        # Docs extracted from upstream material age with their sources. Keyed off
        # `sources` itself rather than a declared source_type: if a doc names
        # upstream material, that material's age is what matters.
        #
        # This runs regardless of `stale_after`. A future expiry is an author's
        # *claim* about when content will rot; it is not evidence that the sources
        # behind it are current, so letting it gate this check would make
        # `stale_after: 2099-01-01` a way to silence the 90/180-day thresholds.
        # A machine-generated doc's source age is a deriver's concern, not a
        # reviewer's: rerunning it cannot move `sources[].last_modified` (that
        # tracks the upstream artifact's own commit date), so a hard fail here
        # would block every PR with no remedy available inside the repo. Warn
        # instead.
        gen = fm.get("generated")
        gen_by = gen.get("by") if isinstance(gen, dict) else None
        machine_generated = isinstance(gen_by, str) and gen_by.startswith("process:")

        slc = oldest_source_date(fm)
        if slc is None and fm.get("sources"):
            # No entry carries `last_modified`, so there is nothing to age. The
            # old schema made `source_last_checked` mandatory, so this gate could
            # never be skipped; keep that property rather than failing open.
            warnings.append(
                f"{rel}: has 'sources' but no entry carries 'last_modified', "
                f"so source freshness cannot be checked"
            )
        if slc is not None:
            age = days_between(today, slc)
            if age > 180 and not machine_generated:
                errors.append(
                    f"{rel}: oldest sources[].last_modified={slc.isoformat()} "
                    f"is {age} days old (>180)"
                )
            elif age > 90:
                warnings.append(
                    f"{rel}: oldest sources[].last_modified={slc.isoformat()} "
                    f"is {age} days old (>90)"
                )

    for w in warnings:
        print(f"  ? freshness warn: {w}")
    if errors:
        print("freshness: FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"freshness: OK ({len(warnings)} warnings)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--today", help="reference date YYYY-MM-DD (default: system today)")
    args = ap.parse_args()
    today = date.fromisoformat(args.today) if args.today else date.today()
    sys.exit(check(Path(args.root).resolve(), today))
