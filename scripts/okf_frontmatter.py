"""Frontmatter parser for personal-okf.

Backed by PyYAML (`yaml.safe_load`). This file is the single source of truth
for parsing in this repo's tooling.

Note on types: PyYAML resolves YAML tags, so `generated: { at: 2026-06-22 }`
comes back as a `datetime.date` and `2026-06-22T10:00:00Z` as a
`datetime.datetime`. Callers validating dates must accept those — see
`coerce_date_str()`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - environment guard
    raise SystemExit(
        "PyYAML is required by the personal-okf verify suite but is not installed.\n"
        "  install it with:  python3 -m pip install -r requirements.txt\n"
        f"  (import failed: {exc})"
    ) from exc


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class FrontmatterError(Exception):
    path: Path
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.path}: {self.message}"


def read_frontmatter(path: Path) -> tuple[dict | None, str]:
    """Return (frontmatter_dict, body). frontmatter_dict is None if no block."""
    return parse_frontmatter_text(path.read_text(encoding="utf-8"), path)


def parse_frontmatter_text(text: str, path: Path | None = None) -> tuple[dict | None, str]:
    """Same as `read_frontmatter`, but from an in-memory string.

    Lets a caller parse frontmatter from a source other than the working tree —
    e.g. `git show HEAD:path` output — without writing a temp file. `path` is
    used only to label a `FrontmatterError`; pass the real path when known.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    body = text[m.end():]
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        raise FrontmatterError(path, _format_yaml_error(e)) from e
    if fm is None:
        return {}, body
    if not isinstance(fm, dict):
        raise FrontmatterError(
            path, f"frontmatter must be a mapping, got {type(fm).__name__}"
        )
    return fm, body


def _format_yaml_error(e: yaml.YAMLError) -> str:
    """Flatten a YAMLError into one line, keeping the line/column if present."""
    problem = getattr(e, "problem", None) or "invalid YAML"
    mark = getattr(e, "problem_mark", None)
    if mark is not None:
        # +2: the frontmatter body starts on the line after the opening `---`,
        # and PyYAML's mark.line is 0-based.
        return f"{problem} (line {mark.line + 2}, column {mark.column + 1})"
    return str(e).replace("\n", " ")


def coerce_date_str(value) -> str | None:
    """Normalise a YAML-parsed date-ish value to an ISO 8601 string.

    PyYAML resolves `2026-06-22` to `datetime.date` and `2026-06-22T10:00:00Z`
    to `datetime.datetime`, so a caller that only accepts `str` would silently
    reject every date in the corpus. Returns None for anything not date-shaped,
    which callers report as malformed.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None


# `sources/` holds raw upstream inputs (discovery-meeting notes, vendor docs,
# partner-facing exports) — the un-curated material authors read *from*, not
# OKF docs. It is intentionally not parsed or frontmatter-checked; files here
# may be non-markdown and carry no frontmatter.
EXCLUDED_DIRS = {
    ".git",
    ".github",
    ".claude",
    "sources",
}


def is_excluded_path(path: Path) -> bool:
    """True if path lives inside a non-OKF directory (.git, .github, sources, …)."""
    return any(part in EXCLUDED_DIRS for part in path.parts)


def iter_markdown_files(root: Path) -> list[Path]:
    return sorted(
        p for p in root.rglob("*.md")
        if not is_excluded_path(p.relative_to(root))
    )


# OKF §8: "Index files contain no frontmatter, with one exception: a bundle-root
# `index.md` MAY carry an `okf_version` key (§12)." So the allowance is scoped to
# the bundle root — a non-root index.md carrying okf_version is non-conformant,
# as is any other key in any reserved file. Shared by okf_conformance.py (layer 1)
# and check_structure.py (layer 5) so the rule has one implementation.
def check_reserved_frontmatter(rel: Path, fm: dict) -> list[str]:
    """Validate a reserved file's frontmatter. `rel` is relative to bundle root."""
    # Both conditions matter: §8 scopes the allowance to the bundle *root* and to
    # `index.md` specifically. Depth alone would also exempt the root `log.md`,
    # which is a reserved file this function is called for.
    is_root = len(rel.parts) == 1 and rel.name == "index.md"
    allowed = {"okf_version"} if is_root else set()
    extra = sorted(set(fm.keys()) - allowed)
    if not extra:
        return []
    if not is_root and "okf_version" in extra:
        return [
            f"{rel}: 'okf_version' is permitted only in the bundle-root index.md "
            f"(OKF §8/§12); remove the frontmatter block from this file"
            + (f"; also found {[k for k in extra if k != 'okf_version']}" if len(extra) > 1 else "")
        ]
    return [
        f"{rel}: reserved file may not carry frontmatter"
        + (" except 'okf_version'" if is_root else "")
        + f"; found {extra}"
    ]
