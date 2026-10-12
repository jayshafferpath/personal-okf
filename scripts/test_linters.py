"""Regression tests for the verify suite's own logic.

Stdlib `unittest`; run directly or via `verify.sh --tests`.

Why this exists: the linters encode rules whose *failure mode is silence*. A
freshness gate that stops matching, or a validator that accepts a malformed
actor, does not announce itself — the suite still prints OK. Every case here is
one that was either a real bug or a plausible-looking claim that had to be
checked by hand; each is pinned so it stays checked.

Tests write frontmatter to a temp dir rather than touching the corpus, so a
failure here means the *logic* regressed, not that a doc changed.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import check_freshness  # noqa: E402
import check_generated_at  # noqa: E402
import check_index_coverage  # noqa: E402
import lint_extensions  # noqa: E402
from okf_frontmatter import (  # noqa: E402
    FrontmatterError,
    check_reserved_frontmatter,
    read_frontmatter,
)

TODAY = date(2026, 8, 11)


def fm_doc(body_fm: str, body: str = "\nBody.\n") -> Path:
    """Write a temp doc with the given frontmatter; return its path."""
    d = Path(tempfile.mkdtemp())
    p = d / "doc.md"
    p.write_text(f"---\n{body_fm.strip()}\n---\n{body}", encoding="utf-8")
    return p


def parse(body_fm: str, body: str = "\nBody.\n") -> dict:
    fm, _ = read_frontmatter(fm_doc(body_fm, body))
    return fm


class TestIndexCoverage(unittest.TestCase):
    """Every direct content document stays reachable from its catalog."""

    def _repo(self, index_body: str, docs: tuple[str, ...] = ("one.md",)) -> Path:
        root = Path(tempfile.mkdtemp())
        folder = root / "concepts"
        folder.mkdir()
        (folder / "index.md").write_text(index_body, encoding="utf-8")
        for doc in docs:
            (folder / doc).write_text("content\n", encoding="utf-8")
        return root

    def _check(self, root: Path) -> int:
        # Expected failures should test the return code without making the
        # normal regression-test output look like the suite failed.
        with contextlib.redirect_stdout(io.StringIO()):
            return check_index_coverage.check(root, content_dirs=("concepts",))

    def test_all_documents_are_catalogued(self):
        root = self._repo("- [one](./one.md)\n")
        self.assertEqual(self._check(root), 0)

    def test_missing_catalog_entry_fails(self):
        root = self._repo("- [one](./one.md)\n", docs=("one.md", "two.md"))
        self.assertNotEqual(self._check(root), 0)

    def test_duplicate_catalog_entry_fails(self):
        root = self._repo("- [one](./one.md)\n- [again](./one.md)\n")
        self.assertNotEqual(self._check(root), 0)

    def test_broken_direct_link_fails(self):
        root = self._repo("- [missing](./missing.md)\n", docs=())
        self.assertNotEqual(self._check(root), 0)

    def test_readme_is_supporting_material(self):
        root = self._repo("- [one](./one.md)\n")
        (root / "concepts" / "README.md").write_text("notes\n", encoding="utf-8")
        self.assertEqual(self._check(root), 0)


class TestFreshnessRecency(unittest.TestCase):
    """`verified[].at` drives the staleness gate (OKF §5.2)."""

    def test_iso_datetime_at_is_parsed(self):
        # PyYAML resolves `2025-01-01T00:00:00Z` to a datetime, not a str. If
        # parse_ymd rejected those, latest_verified would return None for every
        # doc and the 180-day gate would pass silently for the whole corpus.
        fm = parse("verified:\n  - { by: process:x, at: 2025-01-01T00:00:00Z }")
        self.assertEqual(
            check_freshness.latest_verified(fm), date(2025, 1, 1),
            "an ISO datetime verified[].at must yield a date",
        )

    def test_bare_ymd_at_is_parsed(self):
        fm = parse("verified:\n  - { by: human:x, at: 2025-01-01 }")
        self.assertEqual(check_freshness.latest_verified(fm), date(2025, 1, 1))

    def test_latest_wins_not_first(self):
        # §5.2: "'how recently' is the latest `at`".
        fm = parse(
            "verified:\n"
            "  - { by: process:nightly, at: 2025-01-01T00:00:00Z }\n"
            "  - { by: human:x, at: 2026-07-01T00:00:00Z }"
        )
        self.assertEqual(check_freshness.latest_verified(fm), date(2026, 7, 1))

    def test_bare_mapping_treated_as_one_element_list(self):
        # §5.2 says consumers MUST accept this form.
        fm = parse("verified: { by: human:x, at: 2026-07-01T00:00:00Z }")
        self.assertEqual(check_freshness.latest_verified(fm), date(2026, 7, 1))

    def test_absent_verified_is_none_not_crash(self):
        self.assertIsNone(check_freshness.latest_verified(parse("type: concept")))


class TestFreshnessSources(unittest.TestCase):
    """`sources[].last_modified` ages a doc; `stale_after` is independent."""

    def test_oldest_source_wins(self):
        # A doc is only as fresh as its stalest input.
        fm = parse(
            "sources:\n"
            "  - { id: a, resource: http://a, last_modified: 2026-07-01 }\n"
            "  - { id: b, resource: http://b, last_modified: 2025-01-01 }"
        )
        self.assertEqual(check_freshness.oldest_source_date(fm), date(2025, 1, 1))

    def test_sources_without_last_modified_is_none(self):
        # Callers must treat this as "cannot check", not "fresh".
        fm = parse("sources:\n  - { id: a, resource: http://a }")
        self.assertIsNone(check_freshness.oldest_source_date(fm))

    def test_scalar_sources_does_not_crash(self):
        self.assertIsNone(check_freshness.oldest_source_date(parse("sources: nope")))


class TestActorConvention(unittest.TestCase):
    """OKF §7. The `human:` prefix drives trust tiers, so precision matters."""

    def test_valid_actors(self):
        for a in ("human:jshaffer", "process:finance-nightly",
                  "reference_agent/gemini-2.5-pro", "claude-code/opus-5"):
            self.assertRegex(a, lint_extensions.ACTOR_RE, f"{a} should be valid")

    def test_invalid_actors(self):
        # A bare name silently reads as "not human" and downgrades the tier.
        for a in ("jshaffer", "human:", "plainword", "a/b/c", "human:x y"):
            self.assertIsNone(lint_extensions.ACTOR_RE.match(a),
                              f"{a} should be rejected")


class TestMalformedFrontmatterIsReportedNotRaised(unittest.TestCase):
    """Every validator must degrade to a lint error, never a traceback.

    check_file accumulates errors instead of early-exiting, so a later check
    still sees frontmatter an earlier check already rejected.
    """

    CASES = [
        "generated: some-string",
        "generated: [a, b]",
        "verified: nope",
        "verified: [just-a-string]",
        "sources: a-string",
        "sources: [a-string]",
        "tags: notalist",
        "owners: notalist",
    ]

    def test_no_validator_raises(self):
        vocab = {"concept"}
        for case in self.CASES:
            with self.subTest(case=case):
                path = fm_doc(
                    "type: concept\nid: x\ntitle: X\ndescription: d\n"
                    "owners: [t]\ntags: [a]\n"
                    "generated: { by: human:x, at: 2026-07-01T00:00:00Z }\n"
                    + case
                )
                try:
                    errors = lint_extensions.check_file(
                        path, path.parent, vocab, {})
                except Exception as e:  # noqa: BLE001 - that's the point
                    self.fail(f"{case!r} raised {type(e).__name__}: {e}")
                self.assertTrue(errors, f"{case!r} should produce a lint error")


class TestFootnoteAttribution(unittest.TestCase):
    """OKF §5.1: a footnote label is a `sources[].id` join key."""

    def _check(self, body: str, sources: str = ""):
        fm = parse("type: concept\n" + (sources or "sources:\n  - { id: known, resource: http://a }"))
        return lint_extensions._check_footnote_attribution(Path("d.md"), fm, body)

    def test_unresolved_inline_ref_is_flagged(self):
        self.assertTrue(self._check("A claim.[^bogus]\n"))

    def test_resolved_inline_ref_is_clean(self):
        self.assertFalse(self._check("A claim.[^known]\n"))

    def test_definition_line_alone_is_not_flagged(self):
        # A definition restates a label; flagging it would double-report the
        # inline ref we already caught.
        self.assertFalse(self._check("[^dangling]: some note\n"))

    def test_fenced_example_is_not_flagged(self):
        # OKF.md documents the pattern with illustrative footnotes that have no
        # backing sources entry; a doc quoting the schema must not fail lint.
        self.assertFalse(self._check("```markdown\nX.[^ex]\n\n[^ex]: Example\n```\n"))


class TestReservedFrontmatter(unittest.TestCase):
    """OKF §8/§12: `okf_version` is bundle-root `index.md` only."""

    def test_root_index_may_carry_okf_version(self):
        self.assertFalse(check_reserved_frontmatter(
            Path("index.md"), {"okf_version": "0.2"}))

    def test_root_log_may_not(self):
        # Depth alone would exempt this; the filename matters too.
        self.assertTrue(check_reserved_frontmatter(
            Path("log.md"), {"okf_version": "0.2"}))

    def test_non_root_index_may_not(self):
        errs = check_reserved_frontmatter(
            Path("concepts/index.md"), {"okf_version": "0.2"})
        self.assertTrue(errs)
        self.assertIn("bundle-root", errs[0])

    def test_extra_key_rejected_even_at_root(self):
        self.assertTrue(check_reserved_frontmatter(
            Path("index.md"), {"okf_version": "0.2", "title": "nope"}))


class TestParserRejectsInvalidYaml(unittest.TestCase):
    """The hand-rolled parser accepted these silently; PyYAML must not."""

    def test_unquoted_colon_in_value_raises(self):
        # `description: Distinct from ABC: something` — a naive split-on-":"
        # parser would keep the tail and never notice.
        with self.assertRaises(FrontmatterError):
            read_frontmatter(fm_doc("type: concept\ndescription: A: B"))

    def test_non_mapping_frontmatter_raises(self):
        with self.assertRaises(FrontmatterError):
            read_frontmatter(fm_doc("- a\n- b"))

    def test_nested_02_shapes_round_trip(self):
        # The four shapes a hand-rolled parser would mangle. `resource` leaking
        # to the top level was the dangerous one: it is itself a real 0.2 field.
        fm = parse(
            "generated: { by: human:x, at: 2026-08-11T10:00:00Z }\n"
            "verified:\n  - { by: human:x, at: 2026-08-11T10:00:00Z }\n"
            "sources:\n  - id: foo\n    resource: http://a\n    last_modified: 2026-07-02"
        )
        self.assertIsInstance(fm["generated"], dict)
        self.assertEqual(fm["generated"]["by"], "human:x")
        self.assertEqual(len(fm["verified"]), 1)
        self.assertEqual(sorted(fm["sources"][0]), ["id", "last_modified", "resource"])
        self.assertNotIn("resource", fm, "sources[].resource must not leak to top level")


class TestStaleAfterBoundary(unittest.TestCase):
    """§5.5: "A concept is stale when `today >= stale_after`" — inclusive."""

    def _fail(self, today: date) -> bool:
        import subprocess, tempfile
        d = Path(tempfile.mkdtemp())
        (d / "d.md").write_text(
            "---\ntype: concept\nid: x\ntitle: X\ndescription: d\n"
            "owners: [t]\ntags: [a]\n"
            "generated: { by: human:x, at: 2026-01-01T00:00:00Z }\n"
            "stale_after: 2026-08-11\n---\nBody.\n", encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "check_freshness.py"),
             str(d), "--today", today.isoformat()],
            capture_output=True, text=True)
        return r.returncode != 0

    def test_stale_on_the_day_itself(self):
        # Off-by-one here silently under-reports the first doc that uses the field.
        self.assertTrue(self._fail(date(2026, 8, 11)),
                        "a doc is stale ON its stale_after date, not the day after")

    def test_not_stale_the_day_before(self):
        self.assertFalse(self._fail(date(2026, 8, 10)))


class TestMachineGeneratedSourceAge(unittest.TestCase):
    """A `process:`-generated doc's source age must not hard-fail the build.

    `sources[].last_modified` tracks the upstream artifact's own commit date, so
    rerunning a deriver cannot move it — a hard fail would block every PR with
    no remedy available in-repo.
    """

    FM = ("type: integration\nid: x\ntitle: X\ndescription: d\n"
          "owners: [t]\ntags: [a]\n"
          "sources:\n  - {{ id: s, resource: /sources/x.csv, last_modified: 2025-01-01 }}\n"
          "generated: {{ by: {actor}, at: 2026-01-01T00:00:00Z }}\n")

    def _run(self, actor: str):
        import subprocess, tempfile
        d = Path(tempfile.mkdtemp())
        (d / "d.md").write_text(
            f"---\n{self.FM.format(actor=actor)}---\nBody.\n", encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "check_freshness.py"),
             str(d), "--today", "2026-08-11"],
            capture_output=True, text=True)
        return r.returncode, r.stdout

    def test_process_actor_warns_only(self):
        code, out = self._run("process:derive-something")
        self.assertEqual(code, 0, f"machine-generated must not hard-fail:\n{out}")
        self.assertIn("days old", out, "but it should still warn")

    def test_human_actor_still_hard_fails(self):
        # A human-authored doc with a 588-day-old source is a real review debt.
        code, _ = self._run("human:someone")
        self.assertNotEqual(code, 0, "hand-authored stale sources must still fail")


class TestActorTeamPrefix(unittest.TestCase):
    """§7 omits `team:`, but §5.1 and Appendix A both use it for author."""

    def test_team_actor_accepted(self):
        for a in ("team:ga4-docs", "team:finance-fpa"):
            self.assertRegex(a, lint_extensions.ACTOR_RE,
                             f"{a} appears in the spec's own examples")


class TestUnknownTypeWarnsNotFails(unittest.TestCase):
    """§4.1/§11: consumers MUST tolerate unknown types, MUST NOT reject over one."""

    def test_spec_reserved_type_is_a_warning(self):
        path = fm_doc(
            "type: Attested Computation\nid: x\ntitle: X\ndescription: d\n"
            "owners: [t]\ntags: [a]\n"
            "generated: { by: reference_agent/gemini-2.5-pro, at: 2026-06-28T14:00:00Z }"
        )
        out = lint_extensions.check_file(path, path.parent, {"concept"}, {})
        self.assertTrue(out, "should say something")
        self.assertTrue(all(m.startswith(lint_extensions.WARN) for m in out),
                        f"unknown type must warn, not error: {out}")


class TestGeneratedAtFreshnessOnEdit(unittest.TestCase):
    """Layer 7: warn when a body edit lands next to a stale generated.at.

    Needs a real git repo (the check diffs the working tree against HEAD),
    so this sets one up in a temp dir rather than using `fm_doc()`.
    """

    FM = ("type: concept\nid: x\ntitle: X\ndescription: d\n"
          "owners: [t]\ntags: [a]\n"
          "generated: {{ by: {actor}, at: 2026-01-01T00:00:00Z }}\n")

    DEFAULT_AT = "2026-01-01T00:00:00Z"

    def _fm(self, actor: str = "human:x", at: str = DEFAULT_AT) -> str:
        return self.FM.format(actor=actor).replace(self.DEFAULT_AT, at)

    def _repo(self, actor: str = "human:x", at: str = DEFAULT_AT) -> Path:
        import subprocess

        def run(*args):
            # capture_output so this repo's own pre-commit hook chatter
            # doesn't leak into the test runner's stdout.
            subprocess.run(args, cwd=d, check=True, capture_output=True)

        d = Path(tempfile.mkdtemp())
        run("git", "init", "-q")
        run("git", "config", "user.email", "t@t.com")
        run("git", "config", "user.name", "t")
        (d / "doc.md").write_text(
            f"---\n{self._fm(actor, at)}---\nOriginal body.\n",
            encoding="utf-8")
        run("git", "add", "doc.md")
        run("git", "commit", "-q", "-m", "initial")
        return d

    def test_body_change_with_stale_stamp_warns(self):
        d = self._repo()
        (d / "doc.md").write_text(
            f"---\n{self.FM.format(actor='human:x')}---\nChanged body.\n",
            encoding="utf-8")
        warning = check_generated_at.check_file(d / "doc.md", d)
        self.assertIsNotNone(warning, "a body edit next to an unmoved "
                              "generated.at must warn")
        self.assertIn("generated.at", warning)

    def test_body_change_with_bumped_stamp_is_silent(self):
        # This is the fix an agent applies in response to the warning above —
        # confirms it actually clears the warning, not just changes its text.
        d = self._repo()
        fm = self.FM.format(actor="human:x").replace(
            "2026-01-01T00:00:00Z", "2026-08-13T10:00:00Z")
        (d / "doc.md").write_text(f"---\n{fm}---\nChanged body.\n", encoding="utf-8")
        self.assertIsNone(check_generated_at.check_file(d / "doc.md", d),
                          "bumping generated.at must clear the warning")

    def test_frontmatter_only_edit_is_silent(self):
        # Adding a tag doesn't change what the content *says* — nothing for
        # a content-freshness stamp to react to.
        d = self._repo()
        fm = self.FM.format(actor="human:x").replace("tags: [a]", "tags: [a, b]")
        (d / "doc.md").write_text(f"---\n{fm}---\nOriginal body.\n", encoding="utf-8")
        self.assertIsNone(check_generated_at.check_file(d / "doc.md", d),
                          "a frontmatter-only edit must not warn")

    def test_untracked_new_file_is_silent(self):
        # Nothing at HEAD to diff against — authored with today's stamp in
        # the same edit, by construction.
        d = self._repo()
        (d / "new.md").write_text(
            f"---\n{self.FM.format(actor='human:x')}---\nBrand new.\n",
            encoding="utf-8")
        self.assertIsNone(check_generated_at.check_file(d / "new.md", d),
                          "an untracked file has no HEAD version to diff")

    def test_process_generated_doc_is_exempt(self):
        # A deriver rerun is what's supposed to move the stamp; a stale one
        # here is a maintenance gap, not a hand-edit oversight.
        d = self._repo(actor="process:derive-something")
        (d / "doc.md").write_text(
            f"---\n{self.FM.format(actor='process:derive-something')}---\n"
            "Changed body.\n", encoding="utf-8")
        self.assertIsNone(check_generated_at.check_file(d / "doc.md", d),
                          "process:-generated docs are exempt")

    def test_same_day_reedit_of_bare_date_stamp_is_silent(self):
        # A bare-date stamp can't move within its own day, so a second edit
        # on the commit day has no fix to apply — warning would loop the
        # Stop hook forever.
        d = self._repo(at="2026-08-13")
        (d / "doc.md").write_text(
            f"---\n{self._fm(at='2026-08-13')}---\nChanged body.\n",
            encoding="utf-8")
        self.assertIsNone(
            check_generated_at.check_file(d / "doc.md", d, today=date(2026, 8, 13)),
            "a stamp already dated today is current")

    def test_same_day_reedit_of_datetime_stamp_is_silent(self):
        d = self._repo(at="2026-08-13T10:00:00Z")
        (d / "doc.md").write_text(
            f"---\n{self._fm(at='2026-08-13T10:00:00Z')}---\nChanged body.\n",
            encoding="utf-8")
        self.assertIsNone(
            check_generated_at.check_file(d / "doc.md", d, today=date(2026, 8, 13)),
            "the date part of a datetime stamp is what counts")

    def test_stamp_from_yesterday_still_warns(self):
        d = self._repo(at="2026-08-13")
        (d / "doc.md").write_text(
            f"---\n{self._fm(at='2026-08-13')}---\nChanged body.\n",
            encoding="utf-8")
        self.assertIsNotNone(
            check_generated_at.check_file(d / "doc.md", d, today=date(2026, 8, 14)),
            "the same-day exemption must not swallow genuinely stale stamps")

    def test_no_git_repo_does_not_crash(self):
        # Outside any git repo (or before the first commit), there is no
        # HEAD to diff against; must degrade to silent, not raise.
        d = Path(tempfile.mkdtemp())
        (d / "doc.md").write_text(
            f"---\n{self.FM.format(actor='human:x')}---\nBody.\n",
            encoding="utf-8")
        self.assertIsNone(check_generated_at.check_file(d / "doc.md", d))


if __name__ == "__main__":
    # Quiet by default so verify.sh output stays scannable; -v for detail.
    verbosity = 2 if "-v" in sys.argv or "--verbose" in sys.argv else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = runner.run(suite)
    if result.wasSuccessful():
        print(f"linter regression tests: OK ({result.testsRun} tests)")
    else:
        print("linter regression tests: FAIL")
    sys.exit(0 if result.wasSuccessful() else 1)
