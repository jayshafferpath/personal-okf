"""Layer 6: index coverage and catalog integrity.

Every content document must appear exactly once in its directory's index.md.
Direct markdown links in an index must also resolve. This catches the common
failure mode where a document is valid and linked nowhere from the catalog.

README.md is supporting material rather than an OKF document, so it is not
required to appear in an index. Parent indexes may link to child directories;
those links are handled by the general link checker and are outside this
file-to-index parity check.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote


CONTENT_DIRS = (
    "concepts",
    "integrations",
    "pointers",
    "projects",
)

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#]+?)(?:#[^)]*)?\)")
BULLET_RE = re.compile(r"^\s*[-*+]\s+")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "//")
IGNORED_DOCS = {"README.md", "index.md"}


def _direct_index_links(index: Path):
    """Yield (line number, target, resolved path) for direct .md links."""
    for lineno, line in enumerate(index.read_text(encoding="utf-8").splitlines(), 1):
        # Indexes contain explanatory prose and mapping tables with links. Only
        # bullet entries are catalog rows; counting every link would report
        # legitimate cross-references as duplicate catalog entries.
        if not BULLET_RE.match(line):
            continue
        for match in LINK_RE.finditer(line):
            target = unquote(match.group(1).strip()).split("?")[0]
            if not target or target.startswith(EXTERNAL_PREFIXES):
                continue
            resolved = (index.parent / target).resolve()
            if resolved.parent != index.parent.resolve() or resolved.suffix != ".md":
                continue
            yield lineno, target, resolved


def check(root: Path, content_dirs: tuple[str, ...] = CONTENT_DIRS) -> int:
    errors: list[str] = []
    checked_indexes = 0
    checked_docs = 0

    directories = list(content_dirs)
    initiatives_root = root / "initiatives"
    if "initiatives" in content_dirs and initiatives_root.is_dir():
        # Each initiative lives in its own subfolder (initiatives/<id>/) with
        # its own index.md, checked the same way as any other content dir.
        directories.extend(
            f"initiatives/{p.name}"
            for p in sorted(initiatives_root.iterdir())
            if p.is_dir()
        )

    for directory in directories:
        folder = root / directory
        index = folder / "index.md"
        if not folder.is_dir() or not index.is_file():
            # Layer 5 owns missing directories and indexes. Avoid duplicate
            # findings when this layer runs as part of the full suite.
            continue
        checked_indexes += 1

        docs = {
            path.name
            for path in folder.glob("*.md")
            if path.name not in IGNORED_DOCS
        }
        checked_docs += len(docs)
        links: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for lineno, target, resolved in _direct_index_links(index):
            links[resolved.name].append((lineno, target))
            if not resolved.is_file():
                errors.append(
                    f"{directory}/index.md:{lineno}: direct link does not exist: "
                    f"{target}"
                )

        for name in sorted(docs - links.keys()):
            errors.append(
                f"{directory}/index.md: missing catalog entry for {name}"
            )
        for name, occurrences in sorted(links.items()):
            if name in IGNORED_DOCS:
                continue
            if len(occurrences) > 1:
                locations = ", ".join(str(line) for line, _target in occurrences)
                errors.append(
                    f"{directory}/index.md: duplicate catalog entry for {name} "
                    f"(lines {locations})"
                )

    if errors:
        print("index coverage: FAIL")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        f"index coverage: OK ({checked_docs} documents across "
        f"{checked_indexes} indexes)"
    )
    return 0


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    sys.exit(check(root))
