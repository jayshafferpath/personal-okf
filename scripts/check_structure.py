"""Layer 5: structure parity.

Asserts the directory shape OKF expects:
- every content directory has index.md
- root has index.md and log.md
- content-directory index.md files carry no frontmatter at all — `okf_version`
  is bundle-root-only (OKF §8/§12). Shares check_reserved_frontmatter() with
  okf_conformance.py, which applies it across every reserved file; this layer
  is the fast-fail for the content dirs below.
"""

from __future__ import annotations

import sys
from pathlib import Path

from okf_frontmatter import (
    FrontmatterError,
    check_reserved_frontmatter,
    read_frontmatter,
)


CONTENT_DIRS = (
    "concepts",
    "integrations",
    "pointers",
    "projects",
)


def _check_index(root: Path, d: str, errors: list[str]) -> None:
    p = root / d
    if not p.is_dir():
        errors.append(f"missing content directory: {d}")
        return
    idx = p / "index.md"
    if not idx.exists():
        errors.append(f"missing index.md in {d}/")
        return
    try:
        fm, _body = read_frontmatter(idx)
    except FrontmatterError as e:
        errors.append(f"{d}/index.md: unparseable frontmatter: {e.message}")
        return
    if fm is not None:
        errors.extend(check_reserved_frontmatter(idx.relative_to(root), fm))


def check(root: Path) -> int:
    errors: list[str] = []
    for required in ("index.md", "log.md", "README.md", "CLAUDE.md", "OKF.md"):
        if not (root / required).exists():
            errors.append(f"missing top-level file: {required}")
    for d in CONTENT_DIRS:
        _check_index(root, d, errors)

    # Each initiative lives in its own subfolder (initiatives/<id>/), which
    # carries its own index.md following the same reserved-filename rules.
    initiatives_root = root / "initiatives"
    if initiatives_root.is_dir():
        for sub in sorted(p for p in initiatives_root.iterdir() if p.is_dir()):
            _check_index(root, str(sub.relative_to(root)), errors)

    if errors:
        print("structure parity: FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("structure parity: OK")
    return 0


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    sys.exit(check(root))
