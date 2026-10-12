# CLAUDE.md

Personal knowledge bundle in Open Knowledge Format (OKF) 0.2. It records context about Jay's side projects that the code doesn't carry: purpose, how they relate, conventions, gotchas.

## Layout

- `projects/`: one doc per jayshafferpath repo (`type: project`)
- `concepts/`: cross-project conventions (`type: concept`)
- `integrations/`: external systems such as Jira and GitHub (`type: integration`)
- `pointers/`: live sources that are deliberately not mirrored (`type: pointer`)
- `sources/`: raw notes named `YYYY-MM-DD-topic.md`. No frontmatter, not linked from indexes.
- Each content dir has an `index.md` with no frontmatter. The root `index.md` carries only `okf_version: "0.2"`. `log.md` lives at the root only, with one `## YYYY-MM-DD` heading per day.

Add a new type or directory only when a doc doesn't fit an existing one. Record the decision in `log.md`.

## Frontmatter

Required: `type`, `id` (matches the filename stem), `title`, `description`, `owners`, `tags`, `generated: {by, at}`.

- Use `generated.by: human:jay.shaffer` for agent edits made in an interactive session with Jay.
- Use `resource` for the live thing a doc describes (repo URL, Jira project).
- Use `sources` when a doc extracts facts from a file that can drift. Name the canonical file and treat it as winning on conflict.
- Add `verified` only after Jay has actually reviewed a doc. Never set it speculatively.

## Writing rules

- Write short. Include facts a reader can't get from the code in a minute, and link to the code for the rest.
- Single-source anything shared: put it in one doc and link to it everywhere else.
- Don't mirror volatile data (individual tickets, PR lists). Use a pointer with a query.
- Never record secret values. Env var names are fine.
- Every content doc gets exactly one bullet in its directory's `index.md`. Add a `log.md` line for substantive changes.
