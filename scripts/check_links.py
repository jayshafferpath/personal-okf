"""Layer 3: link integrity (warn-only).

OKF §11 explicitly tolerates broken links; this layer prints warnings and
*always exits 0* so the verify suite stays spec-conformant. The signal is
still surfaced for a human (or LLM) consumer to act on.

Walks every .md in the repo, extracts relative markdown links of the form
`[text](relative/path)`, and resolves them. Also computes orphan docs
(no inbound link from anywhere outside their own directory's index.md).
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

from okf_frontmatter import iter_markdown_files


LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#]+?)(?:#[^)]*)?\)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")


def is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "//"))


def check(root: Path) -> int:
    broken: list[str] = []
    above_repo: list[str] = []
    inbound: dict[Path, set[Path]] = defaultdict(set)
    files = iter_markdown_files(root)
    file_set = {p.resolve() for p in files}

    for path in files:
        rel = path.relative_to(root)
        text = path.read_text(encoding="utf-8")
        in_code = False
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_code = not in_code
                continue
            if in_code:
                continue
            scrubbed = INLINE_CODE_RE.sub(lambda mm: " " * len(mm.group(0)), line)
            for m in LINK_RE.finditer(scrubbed):
                target = m.group(1).strip()
                if not target or is_external(target):
                    continue
                # drop query strings just in case
                target = target.split("?")[0]
                # decode percent-escapes (e.g. %20 for spaces in filenames)
                target = unquote(target)
                if target.endswith("/"):
                    target = target + "index.md"
                resolved = (path.parent / target).resolve()
                try:
                    resolved.relative_to(root)
                except ValueError:
                    above_repo.append(f"{rel}:{lineno} -> {target} (escapes repo root)")
                    continue
                if resolved.is_dir():
                    candidate = resolved / "index.md"
                    if candidate.exists():
                        inbound[candidate].add(path.resolve())
                    else:
                        broken.append(f"{rel}:{lineno} -> {target} (directory, no index.md)")
                    continue
                if resolved.suffix == ".md":
                    if resolved in file_set:
                        inbound[resolved].add(path.resolve())
                    elif resolved.exists():
                        # markdown in an excluded dir (e.g. sources/ raw inputs);
                        # it's a valid on-disk target, just not an OKF doc.
                        pass
                    else:
                        broken.append(f"{rel}:{lineno} -> {target}")
                elif resolved.exists():
                    # non-markdown asset exists; fine
                    pass
                else:
                    broken.append(f"{rel}:{lineno} -> {target}")

    orphans: list[str] = []
    for path in files:
        rel = path.relative_to(root)
        if path.name in {"index.md", "log.md", "README.md", "CLAUDE.md", "OKF.md", "MAINTENANCE.md"}:
            continue
        sources = inbound.get(path.resolve(), set())
        # ignore link from the doc's own directory index.md
        own_index = path.parent / "index.md"
        external_sources = sources - {own_index.resolve()}
        if not external_sources:
            orphans.append(str(rel))

    print(f"link integrity (warn-only): {len(broken)} broken, "
          f"{len(above_repo)} escapes, {len(orphans)} orphans")
    for w in broken:
        print(f"  ! broken: {w}")
    for w in above_repo:
        print(f"  ! escape: {w}")
    for w in orphans:
        print(f"  ? orphan (no inbound links outside own directory): {w}")
    return 0


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    sys.exit(check(root))
