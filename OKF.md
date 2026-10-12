# OKF profile for personal-okf

This bundle follows Open Knowledge Format 0.2. Authoring rules are in [CLAUDE.md](CLAUDE.md). This file holds the parts that `scripts/` parses.

## 3. Type vocabulary

- `project`: one personal repo under jayshafferpath.
- `concept`: a convention or term that spans projects.
- `integration`: an external system the projects talk to.
- `pointer`: a live external resource that is deliberately not mirrored. Requires `resource`.
- `decision`: an ADR-style record. Supersede it rather than editing it.
- `runbook`: an operational procedure (setup, recovery, migration).

Adding a type is a deliberate change: add it here and note it in `log.md`.
