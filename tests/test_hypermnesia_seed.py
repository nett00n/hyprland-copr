"""Tests for memory/seed.sql, the HyperMnesia Tier 0/1 component/constraint map (#COPR-0024).

No database needed -- this parses the SQL text itself and checks it against the working
tree, the same way upstream HyperMnesia's `ci/freshness.py` checks a live store: every
`key_paths` glob must match at least one tracked file, every constraint's component
reference must resolve, and slugs must be unique. A glob that matches nothing is exactly
the failure mode this test exists to catch -- Tier 1 answers "no rules apply" instead of
erroring, so nothing else would ever notice.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SEED_SQL = REPO_ROOT / "memory" / "seed.sql"


def _split_top_level_tuples(text: str) -> list[str]:
    """Split a `VALUES (...), (...), (...)` block into its top-level `(...)` tuples.

    Ignores parens/commas inside single-quoted strings (SQL escapes a literal quote as
    `''`, handled below) so a subselect like `(SELECT id FROM components WHERE ...)`
    inside a tuple doesn't get mistaken for a tuple boundary.
    """
    tuples = []
    depth = 0
    in_string = False
    current = []
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "'" and text[i : i + 2] == "''":
                current.append("''")
                i += 2
                continue
            if ch == "'":
                in_string = False
            current.append(ch)
        elif ch == "'":
            in_string = True
            current.append(ch)
        elif ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
            if depth == 0:
                tuples.append("".join(current))
                current = []
        elif depth > 0:
            current.append(ch)
        i += 1
    return tuples


def _find_statement_end(sql: str, start: int) -> int:
    """Return the index of the `;` that ends the statement starting at `start`, ignoring
    any `;` inside a single-quoted string (a constraint statement/rationale can contain
    one, e.g. "...pipeline; the generated files...")."""
    in_string = False
    i = start
    while i < len(sql):
        ch = sql[i]
        if in_string:
            if ch == "'" and sql[i : i + 2] == "''":
                i += 2
                continue
            if ch == "'":
                in_string = False
        elif ch == "'":
            in_string = True
        elif ch == ";":
            return i
        i += 1
    raise AssertionError(f"unterminated SQL statement starting at offset {start}")


def _extract_insert_block(sql: str, table: str) -> str:
    """Return the concatenated text of every `INSERT INTO <table> (...) VALUES ...;`
    block's tuple list -- seed.sql inserts into `components` more than once (parent, then
    leaves), so a single re.search would silently see only the first."""
    blocks = []
    for m in re.finditer(
        rf"INSERT INTO {re.escape(table)}\s*\([^)]*\)\s*VALUES\s*", sql
    ):
        end = _find_statement_end(sql, m.end())
        blocks.append(sql[m.end() : end])
    assert blocks, f"no INSERT INTO {table} (...) VALUES ...; block found in {SEED_SQL}"
    return ",".join(blocks)


def _parse_components(sql: str) -> dict[str, list[str]]:
    """Return {slug: [glob, ...]} for every component row."""
    block = _extract_insert_block(sql, "components")
    components: dict[str, list[str]] = {}
    for tup in _split_top_level_tuples(block):
        inner = tup[1:-1]  # strip outer parens
        slug_match = re.search(r"^'[^']*','([^']+)'", inner)
        assert slug_match, f"could not find slug in component tuple: {tup!r}"
        slug = slug_match.group(1)
        if "'{}'::text[]" in inner:
            components[slug] = []
            continue
        globs_match = re.search(r"ARRAY\[(.*?)\]", inner, re.DOTALL)
        assert globs_match, (
            f"could not find key_paths ARRAY[...] in component tuple: {tup!r}"
        )
        globs_text = globs_match.group(1).strip()
        globs = re.findall(r"'([^']*)'", globs_text) if globs_text else []
        components[slug] = globs
    return components


def _parse_constraint_component_slugs(sql: str) -> list[str | None]:
    """Return the referenced component slug (or None for global) for each constraint row."""
    block = _extract_insert_block(sql, "constraints")
    slugs: list[str | None] = []
    for tup in _split_top_level_tuples(block):
        if "scope='global'" in tup or ",'global'," in tup:
            slugs.append(None)
            continue
        slug_match = re.search(r"slug='([^']+)'\s+AND\s+repo=", tup)
        if slug_match:
            slugs.append(slug_match.group(1))
        else:
            slugs.append(None)
    return slugs


@pytest.fixture(scope="module")
def seed_sql() -> str:
    assert SEED_SQL.exists(), f"{SEED_SQL} does not exist"
    return SEED_SQL.read_text()


@pytest.fixture(scope="module")
def tracked_files() -> set[str]:
    """Files a `key_paths` glob may reasonably match: git-tracked files, plus files git
    ignores but that are still real and edited (CLAUDE.md itself is gitignored globally on
    this box -- see ~/.gitignore -- yet is exactly the kind of path arch_invariants must
    resolve). Tier 0/1 glob resolution runs against whatever path an edit targets, not
    against the doc corpus `hm ingest` enumerates (that one does need `--walk` for anything
    git-ignored, per docs/INSTALL.md); this fixture mirrors the former."""
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    # A handful of top-level paths are real, meant to be edited, and referenced by
    # key_paths, but excluded from `git ls-files` by a personal global gitignore
    # (~/.gitignore ignores CLAUDE.md repo-wide) rather than this repo's own .gitignore.
    extra = [p for p in ("CLAUDE.md",) if (REPO_ROOT / p).is_file()]
    return {line for line in [*tracked, *extra] if line}


@pytest.fixture(scope="module")
def components(seed_sql) -> dict[str, list[str]]:
    return _parse_components(seed_sql)


class TestComponentSlugs:
    def test_at_least_one_component(self, components):
        assert components, "seed.sql defines no components"

    def test_slugs_are_unique(self, seed_sql):
        block = _extract_insert_block(seed_sql, "components")
        slugs = []
        for tup in _split_top_level_tuples(block):
            m = re.search(r"^'[^']*','([^']+)'", tup[1:-1])
            slugs.append(m.group(1))
        assert len(slugs) == len(set(slugs)), f"duplicate component slugs: {slugs}"


class TestKeyPathsResolve:
    """Every glob must match at least one tracked file -- an orphaned glob is a component
    whose rules silently stop being injected the moment a directory moves."""

    def test_every_glob_matches_a_tracked_file(self, components, tracked_files):
        orphans = []
        for slug, globs in components.items():
            for glob in globs:
                if not _glob_matches_any(glob, tracked_files):
                    orphans.append((slug, glob))
        assert not orphans, (
            "orphaned key_paths globs (match no tracked file): "
            + ", ".join(f"{slug}: {glob!r}" for slug, glob in orphans)
        )


class TestConstraintsReferenceRealComponents:
    def test_every_component_scoped_constraint_resolves(self, seed_sql, components):
        referenced = _parse_constraint_component_slugs(seed_sql)
        unresolved = [
            slug for slug in referenced if slug is not None and slug not in components
        ]
        assert not unresolved, (
            f"constraints reference unknown component slugs: {unresolved}"
        )


def _glob_matches_any(glob: str, files: set[str]) -> bool:
    """Match HyperMnesia's glob semantics: `**` crosses `/` (and matches zero segments),
    `*`/`?` do not. Good enough approximation via translation to a regex."""
    pattern = re.escape(glob)
    pattern = pattern.replace(r"\*\*/", "(?:.*/)?")
    pattern = pattern.replace(r"\*\*", ".*")
    pattern = pattern.replace(r"\*", "[^/]*")
    pattern = pattern.replace(r"\?", "[^/]")
    regex = re.compile("^" + pattern + "$")
    return any(regex.match(f) for f in files)
