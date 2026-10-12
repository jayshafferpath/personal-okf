"""Layer 2: personal-okf extension-field lint.

Checks our extensions to the OKF baseline (see OKF.md):

  required everywhere: id, owners, tags, generated
  origin-dependent (see _check_origin): a doc whose body is a pointer rather
    than the content itself MUST carry `resource`
  vocabulary:
    type in TYPE_VOCAB (parsed from OKF.md)
    status in {draft, stable, deprecated} when present (§5.4)
  OKF 0.2 trust fields (§5.2):
    generated: { by, at }   required; `by` must be a §7 actor
    verified: [{ by, at }]  optional (absence = the §5.3 'unverified' tier),
                            validated when present; a bare mapping is accepted
                            as a one-element list per §5.2
  OKF 0.2 provenance (§5.1):
    resource                the concept's own canonical URI
    sources: [{...}]        one entry per upstream artifact; `resource` REQUIRED
                            per entry, `id` kebab-case and unique when present,
                            `author` actor-shaped, `usage_count` an integer
    body footnote [^label]  must resolve to a sources[].id
  retired, and rejected if they reappear:
    timestamp -> generated.at          last_verified -> verified[].at
    external_url -> resource           source_url -> sources[].resource
    source_last_checked -> sources[].last_modified
  formats:
    id matches ^[a-z0-9][a-z0-9-]*$ and is globally unique
    dates parse as YYYY-MM-DD or ISO 8601
    tags is a non-empty list of kebab-case strings
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

from okf_frontmatter import (
    FrontmatterError,
    coerce_date_str,
    is_excluded_path,
    iter_markdown_files,
    read_frontmatter,
)


RESERVED_NAMES = {"index.md", "log.md"}
EXEMPT_TOPLEVEL_NAMES = {"README.md", "CLAUDE.md", "OKF.md", "MAINTENANCE.md"}
# OKF §5.4 lifecycle. Absent ⇒ `stable`, so we validate it but never require it.
STATUS_VALUES = {"draft", "stable", "deprecated"}

# Types whose body is *discovery metadata about somewhere else*, not the content
# itself — an agent must fetch the real thing before quoting a value, so the
# canonical URI is mandatory. `type: integration` legitimately spans owned/
# curated/reference and so is governed by the general rules instead.
POINTER_LIKE_TYPES = {"dashboard", "pointer"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
KEBAB_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# OKF §7 actor convention: `human:<id>` for a person, `process:<id>` for an
# automated process, `<producer>/<version>` for an agent or tool. Consumers key
# trust tiers (§5.3) off the `human:` prefix, so a malformed actor silently
# downgrades a doc's trust — worth failing the build over.
#
# `team:<id>` is accepted too. §7 does not list it, but the spec's own examples
# use it for `sources[].author` (§5.1 `team:ga4-docs`, Appendix A
# `team:finance-fpa`), so rejecting it would fail the canonical v0.2 documents.
ACTOR_RE = re.compile(
    r"^(?:human:[^\s]+|process:[^\s]+|team:[^\s]+|[^\s:/]+/[^\s:/]+)$"
)

# Emitted by check_file with this prefix and split out by check(); §11 forbids a
# consumer rejecting a bundle over these, but we still want them visible.
WARN = "WARN:"


def parse_type_vocab(okf_md: Path) -> set[str]:
    """Parse `## 3. Type vocabulary` bullets out of OKF.md."""
    text = okf_md.read_text(encoding="utf-8")
    m = re.search(r"## 3\. Type vocabulary(.*?)(?:\n## |\Z)", text, re.DOTALL)
    if not m:
        raise RuntimeError("OKF.md: '## 3. Type vocabulary' section missing")
    block = m.group(1)
    types = set(re.findall(r"^-\s+`([a-z0-9-]+)`", block, re.MULTILINE))
    if not types:
        raise RuntimeError("OKF.md: no type bullets parsed from §3")
    return types


def parse_date(value) -> bool:
    """True if `value` is a valid date / ISO 8601 datetime.

    PyYAML already resolves `2026-06-22` to a `date` and `2026-06-22T10:00:00Z`
    to a `datetime`, so those arrive pre-validated; coerce_date_str normalises
    them back to a string. A plain string still has to parse (a doc can quote
    its dates, and a deriver could write them as strings).
    """
    s = coerce_date_str(value)
    if s is None:
        return False
    try:
        if "T" in s:
            datetime.fromisoformat(s.replace("Z", "+00:00"))
        else:
            date.fromisoformat(s)
        return True
    except ValueError:
        return False


def _check_actor(rel: Path, field: str, value) -> list[str]:
    if not isinstance(value, str) or not ACTOR_RE.match(value):
        return [
            f"{rel}: {field} = {value!r} is not a valid OKF §7 actor "
            f"(human:<id> | process:<id> | <producer>/<version>)"
        ]
    return []


def _check_generated(rel: Path, fm: dict) -> list[str]:
    """OKF §5.2: `generated: { by, at }`; `by` REQUIRED and actor-shaped."""
    gen = fm.get("generated")
    if gen is None:
        return [f"{rel}: missing required field 'generated' (OKF §5.2)"]
    if not isinstance(gen, dict):
        return [f"{rel}: 'generated' must be a mapping {{ by, at }}, got "
                f"{type(gen).__name__}"]
    errors: list[str] = []
    if "by" not in gen:
        errors.append(f"{rel}: 'generated.by' is required (OKF §5.2)")
    else:
        errors.extend(_check_actor(rel, "generated.by", gen["by"]))
    at = gen.get("at")
    if at is None:
        errors.append(f"{rel}: 'generated.at' is required")
    elif not parse_date(at):
        errors.append(f"{rel}: 'generated.at' = {at!r} is not ISO 8601")
    unknown = sorted(set(gen) - {"by", "at"})
    if unknown:
        errors.append(f"{rel}: unknown key(s) in 'generated': {unknown}")
    return errors


def _check_verified(rel: Path, fm: dict) -> list[str]:
    """OKF §5.2: a list of `{ by, at }`, or a bare mapping treated as one entry.

    Optional — absence is the §5.3 'unverified' tier, which is conformant.
    """
    ver = fm.get("verified")
    if ver is None:
        return []
    entries = [ver] if isinstance(ver, dict) else ver
    if not isinstance(entries, list) or not entries:
        return [f"{rel}: 'verified' must be a non-empty list of {{ by, at }} "
                f"(or a single mapping)"]
    errors: list[str] = []
    for i, e in enumerate(entries):
        where = f"verified[{i}]"
        if not isinstance(e, dict):
            errors.append(f"{rel}: {where} must be a mapping {{ by, at }}, got "
                          f"{type(e).__name__}")
            continue
        if "by" not in e:
            errors.append(f"{rel}: {where}.by is required")
        else:
            errors.extend(_check_actor(rel, f"{where}.by", e["by"]))
        at = e.get("at")
        if at is None:
            errors.append(f"{rel}: {where}.at is required")
        elif not parse_date(at):
            errors.append(f"{rel}: {where}.at = {at!r} is not ISO 8601")
        unknown = sorted(set(e) - {"by", "at"})
        if unknown:
            errors.append(f"{rel}: unknown key(s) in {where}: {unknown}")
    return errors


def _check_sources(rel: Path, fm: dict) -> list[str]:
    """OKF §5.1: a list of entries, each with a REQUIRED `resource`.

    `id` is optional per the spec but SHOULD be present when the body cites the
    source; we require kebab-case when it is there, since it is the join key for
    footnote attribution and a typo silently misattributes a claim.
    """
    srcs = fm.get("sources")
    if srcs is None:
        return []
    if not isinstance(srcs, list) or not srcs:
        return [f"{rel}: 'sources' must be a non-empty list (OKF §5.1)"]
    known = {"id", "resource", "title", "author", "usage_count",
             "last_modified", "usage_window"}
    errors: list[str] = []
    seen_ids: set[str] = set()
    for i, e in enumerate(srcs):
        where = f"sources[{i}]"
        if not isinstance(e, dict):
            errors.append(f"{rel}: {where} must be a mapping, got {type(e).__name__}")
            continue
        if not e.get("resource"):
            errors.append(f"{rel}: {where}.resource is required (OKF §5.1)")
        sid = e.get("id")
        if sid is not None:
            if not isinstance(sid, str) or not KEBAB_RE.match(sid):
                errors.append(f"{rel}: {where}.id {sid!r} must be kebab-case")
            elif sid in seen_ids:
                errors.append(f"{rel}: duplicate {where}.id {sid!r} — footnote "
                              f"labels must resolve to one entry")
            else:
                seen_ids.add(sid)
        lm = e.get("last_modified")
        if lm is not None and not parse_date(lm):
            errors.append(f"{rel}: {where}.last_modified = {lm!r} is not a date")
        uc = e.get("usage_count")
        if uc is not None and not isinstance(uc, int):
            errors.append(f"{rel}: {where}.usage_count must be an integer")
        if e.get("author") is not None:
            errors.extend(_check_actor(rel, f"{where}.author", e["author"]))
        unknown = sorted(set(e) - known)
        if unknown:
            errors.append(f"{rel}: unknown key(s) in {where}: {unknown}")
    return errors


def _check_origin(rel: Path, fm: dict) -> list[str]:
    """Where a doc's truth lives, expressed in OKF 0.2 terms.

    The origin of a doc is readable from the 0.2 fields themselves:

      generated.by = process:*  ->  machine-generated; its `sources` name the input
      resource present          ->  the truth is the external artifact, fetch it
      sources present           ->  extracted from upstream material, go verify there
      neither                   ->  we author it; no upstream

    Only one rule needs enforcing on top of the shape checks: a doc whose body is
    deliberately *not* the content (a dashboard, a pointer) is useless without a
    URI to follow, so `resource` is mandatory there.
    """
    errors: list[str] = []
    if fm.get("type") in POINTER_LIKE_TYPES and not fm.get("resource"):
        errors.append(
            f"{rel}: type '{fm.get('type')}' documents an external artifact, so "
            f"'resource' is required — the body is discovery metadata, not the "
            f"content itself"
        )
    # `or {}` is not enough: a malformed scalar (`generated: some-string`) is
    # truthy, so .get() would raise AttributeError. _check_generated already
    # reports the shape error, and check_file accumulates rather than early-exits,
    # so this must degrade quietly instead of crashing the whole run.
    gen = fm.get("generated")
    gen_by = gen.get("by") if isinstance(gen, dict) else None
    if isinstance(gen_by, str) and gen_by.startswith("process:") and not fm.get("sources"):
        errors.append(
            f"{rel}: generated.by is {gen_by!r}, so this doc was produced from "
            f"something — declare it in 'sources' (OKF §5.1)"
        )
    return errors


FOOTNOTE_REF_RE = re.compile(r"\[\^([^\]]+)\]")
FOOTNOTE_DEF_RE = re.compile(r"^\s*\[\^([^\]]+)\]:")
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")


def _check_footnote_attribution(rel: Path, fm: dict, body: str) -> list[str]:
    """OKF §5.1: a footnote label used for attribution is a `sources[].id`.

    The point of keying attribution by id rather than position is that it cannot
    misattribute silently — but only if the label actually resolves. A label with
    no matching entry is a citation pointing at nothing.

    Only *inline* references are checked. Definition lines (`[^x]: text`) are
    skipped because they restate a label rather than making a claim, and a
    definition whose reference we already flagged would double-report. Fenced
    blocks are skipped too: OKF.md's own examples contain illustrative footnotes
    that deliberately have no backing `sources` entry.
    """
    srcs = fm.get("sources")
    ids = {
        e.get("id")
        for e in (srcs if isinstance(srcs, list) else [])
        if isinstance(e, dict) and e.get("id")
    }
    unresolved: set[str] = set()
    in_fence = False
    for line in (body or "").splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or FOOTNOTE_DEF_RE.match(line):
            continue
        unresolved |= set(FOOTNOTE_REF_RE.findall(line)) - ids
    return [
        f"{rel}: footnote [^{label}] does not match any sources[].id "
        f"(OKF §5.1); known ids: {sorted(ids) or 'none'}"
        for label in sorted(unresolved)
    ]


def _is_concept_file(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    name = path.name
    if name in RESERVED_NAMES:
        return False
    if name in EXEMPT_TOPLEVEL_NAMES and len(rel.parts) == 1:
        return False
    if name == "README.md":
        return False
    return True


def _collect_ids(root: Path) -> dict[str, list[Path]]:
    """Frontmatter-only scan to map id -> all sightings (relpaths). Cheap."""
    ids: dict[str, list[Path]] = {}
    for path in iter_markdown_files(root):
        if not _is_concept_file(path, root):
            continue
        try:
            fm, _ = read_frontmatter(path)
        except FrontmatterError:
            continue
        if not fm:
            continue
        ident = fm.get("id")
        if isinstance(ident, str):
            ids.setdefault(ident, []).append(path.relative_to(root))
    return ids


def check_file(path: Path, root: Path, type_vocab: set[str],
               id_owners: dict[str, list[Path]]) -> list[str]:
    errors: list[str] = []
    if not _is_concept_file(path, root):
        return errors
    rel = path.relative_to(root)
    try:
        fm, body = read_frontmatter(path)
    except FrontmatterError as e:
        return [f"{rel}: unparseable frontmatter: {e.message}"]
    if fm is None:
        return [f"{rel}: no frontmatter block"]

    for k in ("id", "type", "title", "description", "owners", "tags"):
        if not fm.get(k):
            errors.append(f"{rel}: missing required field '{k}'")

    errors.extend(_check_generated(rel, fm))
    errors.extend(_check_verified(rel, fm))
    errors.extend(_check_sources(rel, fm))
    errors.extend(_check_footnote_attribution(rel, fm, body))

    # OKF §13.1 supersedes `timestamp` with `generated.at` and gives consumers a
    # fallback *to* timestamp only when `generated` is absent. Now that
    # `generated` is required, a lingering `timestamp` is a second source of
    # truth for the same fact.
    for retired, replacement in (("timestamp", "generated.at"),
                                 ("last_verified", "verified[].at"),
                                 ("external_url", "resource"),
                                 ("source_url", "sources[].resource"),
                                 ("source_last_checked", "sources[].last_modified"),
                                 ("generated_from", "sources[].resource"),
                                 ("generated_at", "generated.at"),
                                 ("source_type", "generated.by / resource / sources"),
                                 ("confidence", "verified[] recency (no OKF equivalent)")):
        if fm.get(retired) is not None:
            errors.append(
                f"{rel}: '{retired}' is retired; use '{replacement}' "
                f"(OKF §5.1/§5.2, §13.1)"
            )

    t = fm.get("type")
    if t and t not in type_vocab:
        # §4.1/§11: consumers MUST tolerate unknown types and MUST NOT reject a
        # bundle over one. Our closed vocabulary is a local authoring guard
        # against typos, so it warns rather than failing — a doc using a
        # spec-reserved type stays conformant.
        errors.append(
            f"{WARN} {rel}: type '{t}' is not in this repo's vocabulary "
            f"(OKF.md §3): {sorted(type_vocab)}. Add it there if intentional."
        )

    status = fm.get("status")
    if status is not None and status not in STATUS_VALUES:
        errors.append(f"{rel}: status '{status}' not in {sorted(STATUS_VALUES)} "
                      f"(OKF §5.5)")

    sa = fm.get("stale_after")
    if sa is not None and not parse_date(sa):
        errors.append(f"{rel}: 'stale_after' = {sa!r} is not a date (OKF §5.5)")

    ident = fm.get("id")
    if isinstance(ident, str):
        if not ID_RE.match(ident):
            errors.append(f"{rel}: id '{ident}' must match {ID_RE.pattern}")
        else:
            others = [p for p in id_owners.get(ident, []) if p != rel]
            if others:
                errors.append(
                    f"{rel}: duplicate id '{ident}' (also in "
                    f"{', '.join(str(p) for p in others)})"
                )

    tags = fm.get("tags")
    if tags is not None:
        if not isinstance(tags, list) or not tags:
            errors.append(f"{rel}: 'tags' must be a non-empty list")
        else:
            for tag in tags:
                if not isinstance(tag, str) or not KEBAB_RE.match(tag):
                    errors.append(f"{rel}: tag {tag!r} must be kebab-case")

    owners = fm.get("owners")
    if owners is not None and (not isinstance(owners, list) or not owners):
        errors.append(f"{rel}: 'owners' must be a non-empty list")

    errors.extend(_check_origin(rel, fm))

    return errors


def check(root: Path, only: list[Path] | None = None) -> int:
    type_vocab = parse_type_vocab(root / "OKF.md")
    id_owners = _collect_ids(root)
    paths = only if only is not None else iter_markdown_files(root)
    found: list[str] = []
    for path in paths:
        found.extend(check_file(path, root, type_vocab, id_owners))
    warnings = [f[len(WARN):].strip() for f in found if f.startswith(WARN)]
    errors = [f for f in found if not f.startswith(WARN)]
    for w in warnings:
        print(f"  ? lint warn: {w}")
    if errors:
        print("personal-okf extension lint: FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"personal-okf extension lint: OK ({len(warnings)} warnings)")
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
                    help="check only these paths (id-uniqueness still global)")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    only = _resolve_targets(root, args.changed) if args.changed is not None else None
    sys.exit(check(root, only=only))
