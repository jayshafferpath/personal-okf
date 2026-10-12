"""Layer 1: OKF SPEC §9 conformance check.

Models the same rules Google's reference-agent `validate` subcommand enforces
(PR #125 against GoogleCloudPlatform/knowledge-catalog):

  §9.1: every non-reserved .md has parseable YAML frontmatter
  §9.2: every frontmatter has non-empty `type` field
  §8/§12: reserved files (index.md, log.md) carry no frontmatter, except the
          bundle-root index.md which MAY carry `okf_version` — and only it

Plus our --strict equivalent (SPEC §4.1 recommended fields):
  title, description, generated  (0.2 replaced `timestamp` with `generated`,
  §13.1; the shape of `generated` is checked in layer 2)

Exits non-zero on any violation. Requires PyYAML (see `requirements.txt`);
`okf_frontmatter` imports it at module load.

When the official Google validator merges and stabilises, swap this for
`python -m reference_agent validate --bundle . --strict`. Until then,
this script holds the line locally.
SOURCE_REFERENCE: https://github.com/GoogleCloudPlatform/knowledge-catalog/pull/125
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from okf_frontmatter import (
    FrontmatterError,
    check_reserved_frontmatter,
    is_excluded_path,
    iter_markdown_files,
    read_frontmatter,
)


RESERVED_NAMES = {"index.md", "log.md"}
EXEMPT_NAMES = {"README.md", "CLAUDE.md", "OKF.md", "MAINTENANCE.md"}
STRICT_REQUIRED = ("title", "description", "generated")


def check_file(path: Path, root: Path) -> list[str]:
    """Conformance check for one file. Returns a list of error strings."""
    errors: list[str] = []
    rel = path.relative_to(root)
    name = path.name
    if name in EXEMPT_NAMES and len(rel.parts) == 1:
        return errors
    if name == "README.md":
        return errors
    try:
        fm, _body = read_frontmatter(path)
    except FrontmatterError as e:
        return [f"{rel}: unparseable frontmatter: {e.message}"]
    if name in RESERVED_NAMES:
        if fm is None:
            return errors
        errors.extend(check_reserved_frontmatter(rel, fm))
        return errors
    if fm is None:
        return [f"{rel}: missing frontmatter block (§9.1)"]
    t = fm.get("type")
    if not t or (isinstance(t, str) and not t.strip()):
        errors.append(f"{rel}: missing or empty 'type' (§9.2)")
    for k in STRICT_REQUIRED:
        v = fm.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            errors.append(f"{rel}: missing or empty '{k}' (§4.1 strict)")
    return errors


def check(root: Path, only: list[Path] | None = None) -> int:
    paths = only if only is not None else iter_markdown_files(root)
    errors: list[str] = []
    for path in paths:
        errors.extend(check_file(path, root))
    if errors:
        print("OKF §9 conformance: FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("OKF §9 conformance: OK")
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
    args = ap.parse_args()
    root = Path(args.root).resolve()
    only = _resolve_targets(root, args.changed) if args.changed is not None else None
    sys.exit(check(root, only=only))
