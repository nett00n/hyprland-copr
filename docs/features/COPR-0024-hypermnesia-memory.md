# COPR-0024. Agent memory via HyperMnesia (Tier 0/1 constraints + doc search)

**Tags:** #tooling #docs #agents

## User Story

As a maintainer working with an AI coding agent on this repo, I want the hard rules in
`CLAUDE.md`/`docs/` delivered automatically to the agent before it edits a file — rather
than relying on the whole of `CLAUDE.md` staying pinned in context and the agent
remembering to grep `docs/` — so a rule like "never edit `submodules/` sources" or "every
top-level function carries its `#COPR-NNNN`" is not something the agent can silently drop
once context fills up.

## Behavior

An external, self-hosted memory store ([HyperMnesia](https://github.com/Recluse/HyperMnesia),
cloned at `~/personal-env/hypermnesia`, not vendored into this repo) provides three things to
an agent working in this repo, keyed by the scope tag `hyprland-copr-daily`:

- **Tier 0/1 — architectural constraints.** A hand-authored component map
  (`memory/seed.sql`) maps `key_paths` globs to components (`copr-pipeline`, `copr-lib`,
  `copr-config`, `copr-templates`, `copr-vendored`, `copr-docs`, `copr-tests`) and attaches
  `must`/`should` constraints to each. Before an `Edit`/`Write`/`MultiEdit`, a `PreToolUse`
  hook (`arch_invariants.py`) resolves the target path to its component and injects the
  `must` constraints as context — deterministically, without the agent having to search or
  remember to ask.
- **Tier 2 — doc search.** `docs/**.md` is chunked, embedded (bge-m3), and indexed for
  hybrid (vector + full-text) search, exposed via MCP tools (`search_docs`, `get_document`).
- **Personal memory.** Session transcripts are distilled into durable facts and recalled on
  `SessionStart`/`UserPromptSubmit`, replacing the ad-hoc per-user memory file that
  previously served this role.

Every hook is **fail-open**: an unreachable store, an unparseable map, or a scope that
resolves to nothing never blocks an edit — it announces the fault once per session and lets
the agent continue. `arch_invariants.py` deliberately emits no `permissionDecision`, so it
can never auto-approve an edit.

`CLAUDE.md` remains the authoritative, human-readable contract. `memory/seed.sql` is a
hand-maintained *projection* of it into the map format — changing a rule means editing
`CLAUDE.md` first, then updating the seed to match; the seed is never the source of truth.

## Implementation

- `memory/seed.sql` (new, this repo): the component/constraint seed described above.
  Idempotent (`DELETE ... WHERE repo='hyprland-copr-daily'` then re-insert), loaded with
  `psql "$DATABASE_URL" -f memory/seed.sql`.
- `tests/test_hypermnesia_seed.py` (new): parses the seed and checks every `key_paths` glob
  matches at least one file under `git ls-files`, every constraint's `component_id` resolves
  to a component defined in the same file, and slugs are unique. Runs with no database —
  the local mirror of upstream's `ci/freshness.py`.
- `.mcp.json` (new): registers the `hypermnesia` MCP server
  (`~/personal-env/hypermnesia/mcp-server/target/release/hypermnesia-mcp`), scoped via
  `HM_REPO=hyprland-copr-daily`.
- `.claude/settings.json` (new): wires `PreToolUse` (`arch_invariants.py`), `SessionStart`
  (`mem_profile.py`), `UserPromptSubmit` (`mem_recall.py`), `SessionEnd`/`PreCompact`
  (`mem_capture.py`) — all pointed at the venv interpreter in
  `~/personal-env/hypermnesia/.venv`.
- `Makefile`: `memory-refresh` target — `hm ingest` + `ci/freshness.py` + `hm doctor` against
  the external HyperMnesia checkout; no-ops cleanly when `DATABASE_URL` is unset so a box
  with no store configured is unaffected.
- The store itself (Postgres+pgvector, TEI embedder) runs outside this repo, under rootless
  podman compose, per `~/personal-env/hypermnesia/deploy/docker/`. Nothing about bringing it
  up lives in this repo beyond the `memory-refresh` target, which assumes it is already
  running.

## Quirks & Decisions

- **Host is Fedora Atomic (rpm-ostree)** — no package is layered onto the host image for
  this. `psql` comes from a `toolbox` container (`toolbox create hm`) behind a
  `~/.local/bin/psql` shim; the store runs under rootless `podman compose`, not
  `docker compose`, since a `PreToolUse` hook has no TTY to answer a `sudo` prompt.
- **Scope tag is `hyprland-copr-daily`, exact-case, everywhere** (`HM_REPO` in both the hook
  env and the MCP env). The alternative — relying on the cwd-basename fallback — was rejected
  because it silently resolves to nothing the moment the checkout directory is renamed.
- **The seed restates part of `CLAUDE.md` in a different format.** This is deliberate
  duplication, not a new source of truth; `CLAUDE.md` wins on conflict, and the seed is
  expected to be hand-updated whenever `CLAUDE.md` changes.
- **No reranker, no Ollama.** The corpus (`docs/`, ~4.5k lines) is small enough that plain
  RRF (vector + full-text fusion) is sufficient, and CPU-only TEI embeds it in minutes; a GPU
  embedder (the box has `nvidia-container-toolkit`) is a future option, not a requirement.
  Memory distillation uses the `claude` CLI (`HM_LLM_BACKEND=cli`) rather than standing up a
  local model server.
- **HyperMnesia itself is not vendored** — it lives at `~/personal-env/hypermnesia`, cloned
  once, outside this repo's `submodules/`. That keeps `#COPR-0011`'s "vendored sources are
  read-only, edit via pre-build actions" rule from applying to a tool this repo doesn't ship.

## Testing

- Unit (`tests/test_hypermnesia_seed.py`): every glob resolves against tracked files; every
  constraint's component exists; no duplicate slugs.
- Manual/integration (documented in `docs/operations.md`): `hm doctor` / `ci/doctor.py`
  clean; `arch_invariants.py` actually injects the vendored-sources `must` for a
  `submodules/**` path and the `#COPR-NNNN` docstring `must` for a `scripts/lib/**` path;
  killing the store leaves edits working with one visible warning, not silence.

## Status

Planned — infrastructure and seed authored; not yet wired into a live session on this box.
