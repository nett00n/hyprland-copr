"""Unit tests for release autoincrement and autoreset logic."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
import yaml

from lib import build_db, paths, yaml_utils
from lib.yaml_utils import dump_yaml_pretty, update_package_releases

TARGET = "fedora-44-x86_64"


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    """Point lib.paths.BUILD_DB at a fresh tmp file and close the cached connection after."""
    db_path = tmp_path / "build-report.db"
    monkeypatch.setattr(paths, "BUILD_DB", db_path)
    yield db_path
    build_db.close()


@pytest.fixture
def packages_yaml(tmp_path, monkeypatch):
    """Point lib.yaml_utils.PACKAGES_YAML at a fresh tmp file.

    Patched on the yaml_utils module attribute, not lib.paths -- yaml_utils.py
    imports PACKAGES_YAML directly into its own namespace, so patching
    lib.paths would not redirect update_package_releases()'s write.
    """
    path = tmp_path / "packages.yaml"
    monkeypatch.setattr(yaml_utils, "PACKAGES_YAML", path)
    return path


@pytest.fixture
def _run(packages_yaml):
    """Seed packages.yaml from the `packages` dict, then run the real function.

    update_package_releases() now reads/writes packages.yaml for real (BUG-0011
    fix), so every call site needs an on-disk file matching its `packages` arg.
    """

    def run(packages: dict) -> dict:
        packages_yaml.write_text("---\n" + dump_yaml_pretty(packages))
        return update_package_releases(packages, TARGET)

    return run


def _seed(pkg: str, stage: str, hashes: dict | None = None, force_run: int = 0, state: str = "success") -> None:
    """Seed a stage row, optionally with hashes (which requires state=success)."""
    run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
    build_db.set_stage(pkg, stage, TARGET, run_id, state, force_run=force_run)
    if hashes is not None:
        build_db.finalize_stage(pkg, stage, TARGET, started_at=1, hashes=hashes)


class TestUpdatePackageReleases:
    """Test release auto-increment and autoreset logic."""

    def test_first_run_no_stored_hash(self, _run):
        """First run (no stored hash) → needs_rebuild=True, release bumped."""
        packages = {
            "test-pkg": {
                "version": "1.0",
                "release": 1,
                "license": "GPLv3",
                "summary": "Test",
                "description": "Test pkg",
                "url": "https://example.com",
            }
        }

        updates = _run(packages)
        # First run, no stored content_hash → package needs rebuild
        # Release must be bumped: 1 → 2
        assert updates == {"test-pkg": 2}

    def test_content_unchanged_no_force(self, _run):
        """Content unchanged, no force_run → no update."""
        from lib.cache import compute_input_hashes

        pkg_dict = {
            "version": "1.0",
            "release": 2,
            "license": "GPLv3",
            "summary": "Test",
            "description": "Test pkg",
            "url": "https://example.com",
        }
        packages = {"test-pkg": pkg_dict}

        # Compute the actual full input hash set for this package
        actual_hashes = compute_input_hashes("test-pkg", pkg_dict, packages)

        _seed(
            "test-pkg",
            "spec",
            hashes=actual_hashes,  # <- matches computed
        )

        updates = _run(packages)
        # Content unchanged, no cascade → no update
        assert updates == {}

    def test_content_changed_same_version(self, _run):
        """Content changed, version same → release += 1."""
        packages = {
            "test-pkg": {
                "version": "1.0",
                "release": 2,
                "license": "GPLv3",
                "summary": "Test",
                "description": "Test pkg (modified)",  # <- differs from stored
                "url": "https://example.com",
            }
        }
        _seed(
            "test-pkg",
            "spec",
            hashes={"content": "old_hash", "package_version": "1.0"},  # <- doesn't match computed
        )

        updates = _run(packages)
        assert "test-pkg" in updates
        assert updates["test-pkg"] == 3  # 2 + 1

    def test_content_changed_version_changed(self, _run):
        """Content differs, version differs → release resets to 1."""
        packages = {
            "test-pkg": {
                "version": "2.0",  # <- version bumped
                "release": 5,
                "license": "GPLv3",
                "summary": "Test",
                "description": "Test pkg",
                "url": "https://example.com",
            }
        }
        _seed(
            "test-pkg",
            "spec",
            hashes={"content": "old_hash", "package_version": "1.0"},  # <- version was 1.0
        )

        updates = _run(packages)
        assert "test-pkg" in updates
        assert updates["test-pkg"] == 1  # Reset on version change

    def test_release_is_zero(self, _run):
        """release == 0 → treated as version_changed → release = 1."""
        packages = {
            "test-pkg": {
                "version": "1.0",
                "release": 0,  # <- reset signal
                "license": "GPLv3",
                "summary": "Test",
                "description": "Test pkg",
                "url": "https://example.com",
            }
        }
        _seed(
            "test-pkg",
            "spec",
            hashes={"content": "current_hash", "package_version": "1.0"},  # <- same version
        )

        updates = _run(packages)
        assert "test-pkg" in updates
        assert updates["test-pkg"] == 1

    def test_release_is_autorelease_string(self, _run):
        """release='%autorelease' (bad int conversion) → fallback to 1."""
        packages = {
            "test-pkg": {
                "version": "1.0",
                "release": "%autorelease",  # <- can't convert to int
                "license": "GPLv3",
                "summary": "Test",
                "description": "Test pkg",
                "url": "https://example.com",
            }
        }
        _seed(
            "test-pkg",
            "spec",
            hashes={"content": "old_hash", "package_version": "1.0"},  # <- differs → needs rebuild
        )

        updates = _run(packages)
        assert "test-pkg" in updates
        assert updates["test-pkg"] == 1  # Fallback

    def test_force_run_in_spec_stage(self, _run):
        """force_run=True in spec stage → release += 1."""
        packages = {
            "test-pkg": {
                "version": "1.0",
                "release": 2,
                "license": "GPLv3",
                "summary": "Test",
                "description": "Test pkg",
                "url": "https://example.com",
            }
        }
        _seed(
            "test-pkg",
            "spec",
            hashes={"content": "current_hash", "package_version": "1.0"},
            force_run=1,  # <- operator forced rebuild
        )

        updates = _run(packages)
        assert "test-pkg" in updates
        assert updates["test-pkg"] == 3  # 2 + 1

    def test_force_run_in_mock_stage(self, _run):
        """force_run=True in any downstream stage → release += 1."""
        packages = {
            "test-pkg": {
                "version": "1.0",
                "release": 2,
                "license": "GPLv3",
                "summary": "Test",
                "description": "Test pkg",
                "url": "https://example.com",
            }
        }
        _seed(
            "test-pkg", "spec", hashes={"content": "current_hash", "package_version": "1.0"}
        )
        _seed("test-pkg", "mock", force_run=1)  # <- forced in downstream stage

        updates = _run(packages)
        assert "test-pkg" in updates
        assert updates["test-pkg"] == 3  # 2 + 1

    def test_dep_rebuild_cascades(self, _run):
        """pkg A content changed → dep B (depends_on: [A]) release increments."""
        packages = {
            "pkg-a": {
                "version": "1.0",
                "release": 1,
                "license": "GPLv3",
                "summary": "A",
                "description": "A",
                "url": "https://example.com/a",
            },
            "pkg-b": {
                "version": "1.0",
                "release": 2,
                "depends_on": ["pkg-a"],  # <- depends on A
                "license": "GPLv3",
                "summary": "B",
                "description": "B",
                "url": "https://example.com/b",
            },
        }
        _seed("pkg-a", "spec", hashes={"content": "old_hash_a", "package_version": "1.0"})
        _seed("pkg-b", "spec", hashes={"content": "current_hash_b", "package_version": "1.0"})

        updates = _run(packages)
        assert "pkg-a" in updates
        assert updates["pkg-a"] == 2  # A's content changed
        assert "pkg-b" in updates
        assert updates["pkg-b"] == 3  # B cascaded (2 + 1)

    def test_dep_chain_cascade(self, _run):
        """A → B → C: A content changed → B and C cascade."""
        packages = {
            "pkg-a": {
                "version": "1.0",
                "release": 1,
                "license": "GPLv3",
                "summary": "A",
                "description": "A",
                "url": "https://example.com/a",
            },
            "pkg-b": {
                "version": "1.0",
                "release": 1,
                "depends_on": ["pkg-a"],
                "license": "GPLv3",
                "summary": "B",
                "description": "B",
                "url": "https://example.com/b",
            },
            "pkg-c": {
                "version": "1.0",
                "release": 1,
                "depends_on": ["pkg-b"],
                "license": "GPLv3",
                "summary": "C",
                "description": "C",
                "url": "https://example.com/c",
            },
        }
        _seed("pkg-a", "spec", hashes={"content": "old_hash_a", "package_version": "1.0"})
        _seed("pkg-b", "spec", hashes={"content": "current_hash_b", "package_version": "1.0"})
        _seed("pkg-c", "spec", hashes={"content": "current_hash_c", "package_version": "1.0"})

        updates = _run(packages)
        assert updates["pkg-a"] == 2  # A changed
        assert updates["pkg-b"] == 2  # B cascaded
        assert updates["pkg-c"] == 2  # C cascaded

    def test_independent_pkg_not_cascaded(self, _run):
        """pkg A rebuilt, pkg B has no depends_on A → B release unchanged."""
        from lib.cache import compute_input_hashes

        pkg_a = {
            "version": "1.0",
            "release": 1,
            "license": "GPLv3",
            "summary": "A",
            "description": "A",
            "url": "https://example.com/a",
        }
        pkg_b = {
            "version": "1.0",
            "release": 2,
            "depends_on": [],  # <- no dependency on A
            "license": "GPLv3",
            "summary": "B",
            "description": "B",
            "url": "https://example.com/b",
        }
        packages = {"pkg-a": pkg_a, "pkg-b": pkg_b}

        _seed("pkg-a", "spec", hashes={"content": "old_hash_a", "package_version": "1.0"})
        _seed(
            "pkg-b",
            "spec",
            hashes=compute_input_hashes("pkg-b", pkg_b, packages),  # <- matches
        )

        updates = _run(packages)
        assert "pkg-a" in updates
        assert "pkg-b" not in updates  # B not affected

    def test_no_stored_entry_for_dep(self, _run):
        """dep missing from the DB → treated as first-run, cascades."""
        from lib.cache import _content_hash

        pkg_a = {
            "version": "1.0",
            "release": 1,
            "license": "GPLv3",
            "summary": "A",
            "description": "A",
            "url": "https://example.com/a",
        }
        pkg_b = {
            "version": "1.0",
            "release": 1,
            "depends_on": ["pkg-a"],
            "license": "GPLv3",
            "summary": "B",
            "description": "B",
            "url": "https://example.com/b",
        }
        packages = {"pkg-a": pkg_a, "pkg-b": pkg_b}

        # pkg-a has no spec row at all (first run for A)
        _seed("pkg-b", "spec", hashes={"content": _content_hash(pkg_b), "package_version": "1.0"})

        updates = _run(packages)
        # pkg-a: first run, no stored entry → needs_rebuild=True → release 1 + 1 = 2
        assert "pkg-a" in updates
        assert updates["pkg-a"] == 2
        # pkg-b: cascaded from pkg-a rebuild → needs_rebuild=True → release 1 + 1 = 2
        assert "pkg-b" in updates
        assert updates["pkg-b"] == 2

    def test_multiple_deps_one_changed(self, _run):
        """pkg has multiple deps, only one changed → pkg release increments once."""
        from lib.cache import compute_input_hashes

        dep1 = {
            "version": "1.0",
            "release": 1,
            "license": "GPLv3",
            "summary": "Dep1",
            "description": "Dep1",
            "url": "https://example.com/dep1",
        }
        dep2 = {
            "version": "1.0",
            "release": 1,
            "license": "GPLv3",
            "summary": "Dep2",
            "description": "Dep2",
            "url": "https://example.com/dep2",
        }
        pkg = {
            "version": "1.0",
            "release": 5,
            "depends_on": ["dep-1", "dep-2"],
            "license": "GPLv3",
            "summary": "Pkg",
            "description": "Pkg",
            "url": "https://example.com/pkg",
        }
        packages = {"dep-1": dep1, "dep-2": dep2, "pkg": pkg}

        _seed("dep-1", "spec", hashes={"content": "old_hash_dep1", "package_version": "1.0"})
        _seed(
            "dep-2",
            "spec",
            hashes=compute_input_hashes("dep-2", dep2, packages),  # <- matches
        )
        _seed("pkg", "spec", hashes={"content": "old_hash_pkg", "package_version": "1.0"})

        updates = _run(packages)
        assert updates["dep-1"] == 2
        assert "dep-2" not in updates
        assert updates["pkg"] == 6  # cascaded from dep-1 (5 + 1)

    def test_release_lock_prevents_auto_increment(self, _run):
        """release_lock: true → package skipped, release not updated."""
        pkg_dict = {
            "version": "1.0",
            "release": 5,
            "release_lock": True,
            "license": "GPLv3",
            "summary": "Test",
            "description": "Test pkg (modified)",
            "url": "https://example.com",
        }
        packages = {"test-pkg": pkg_dict}

        _seed("test-pkg", "spec", hashes={"content": "old_hash", "package_version": "1.0"})

        updates = _run(packages)
        # release_lock=True → skipped, no update
        assert updates == {}

    def test_release_lock_with_version_change(self, _run):
        """release_lock: true prevents reset even on version change."""
        pkg_dict = {
            "version": "2.0",  # <- version changed
            "release": 5,
            "release_lock": True,
            "license": "GPLv3",
            "summary": "Test",
            "description": "Test pkg",
            "url": "https://example.com",
        }
        packages = {"test-pkg": pkg_dict}

        _seed("test-pkg", "spec", hashes={"content": "old_hash", "package_version": "1.0"})

        updates = _run(packages)
        # release_lock=True → skipped even though version changed
        assert updates == {}

    def test_dependency_release_change_does_not_cascade(self):
        """Dependency release change alone does NOT cascade to dependents.

        This verifies the fix for "metadata is still old" issue where release
        changes in dependencies would incorrectly trigger dependent package rebuilds.

        The dependency hash (used to detect content changes) excludes release,
        so only actual content changes cascade, not release-only changes.
        """
        from lib.cache import _content_hash

        # #BUG-0098: _dependencies_hashes() now uses _content_hash() directly --
        # the formerly-separate _package_config_hash() was byte-identical and
        # has been removed.

        # Dependency package
        dep = {
            "version": "1.0",
            "release": 1,
            "license": "MIT",
            "summary": "Dependency",
            "description": "Dep",
            "url": "https://example.com/dep",
        }

        # Dependent package that depends on dep
        pkg = {
            "version": "2.0",
            "release": 1,
            "depends_on": ["dep"],
            "license": "MIT",
            "summary": "Package",
            "description": "Pkg",
            "url": "https://example.com/pkg",
        }

        packages = {"dep": dep, "pkg": pkg}

        # Build dependency with release=1
        all_packages_1 = {"dep": dep, "pkg": pkg}
        dep_hash_1 = _content_hash(dep)

        # Now bump dependency release to 2
        dep_bumped = dict(dep)
        dep_bumped["release"] = 2
        all_packages_2 = {"dep": dep_bumped, "pkg": pkg}
        dep_hash_2 = _content_hash(dep_bumped)

        # Verify: dependency hash should NOT change with release-only change
        assert dep_hash_1 == dep_hash_2, (
            "Release-only change should not affect dependency hash "
            "(prevents unnecessary cascades)"
        )


class TestUpdatePackageReleasesWritesFile:
    """Regression coverage for BUG-0011: the write to packages.yaml itself.

    update_package_releases() used to rewrite packages.yaml via a
    MULTILINE|DOTALL regex over the raw text. If a package block didn't have
    a `release:` key at exactly two-space indent, the non-greedy `.*?` ran
    past that block's end and rewrote the *next* package's release (or, on a
    trailing comment / different indent, silently no-op'd) while still
    reporting the update as done. These tests exercise the load/mutate/dump
    replacement directly against a real on-disk packages.yaml.
    """

    def test_neighbour_not_corrupted_when_release_key_missing(self, packages_yaml):
        """A malformed package block must not bleed into the next one."""
        from lib.cache import compute_input_hashes

        packages = {
            "pkg-a": {
                "version": "1.0",
                "release": 1,
                "license": "GPLv3",
                "summary": "A",
                "description": "A",
                "url": "https://example.com/a",
            },
            "pkg-b": {
                "version": "1.0",
                "release": 9,
                "license": "GPLv3",
                "summary": "B",
                "description": "B",
                "url": "https://example.com/b",
            },
        }
        _seed("pkg-a", "spec", hashes={"content": "old_hash_a", "package_version": "1.0"})
        # pkg-b's content matches what's stored -> no rebuild, no release change
        # for it; isolates the assertion to pkg-a's write not bleeding over.
        _seed(
            "pkg-b",
            "spec",
            hashes=compute_input_hashes("pkg-b", packages["pkg-b"], packages),
        )

        # Simulate a malformed on-disk block for pkg-a: no `release:` key at all.
        # The old regex would have run its non-greedy `.*?` straight through
        # into pkg-b's block and rewritten pkg-b's release instead.
        on_disk_packages = {
            "pkg-a": {k: v for k, v in packages["pkg-a"].items() if k != "release"},
            "pkg-b": dict(packages["pkg-b"]),
        }
        packages_yaml.write_text("---\n" + dump_yaml_pretty(on_disk_packages))

        updates = update_package_releases(packages, TARGET)
        assert updates == {"pkg-a": 2}

        on_disk = yaml.safe_load(packages_yaml.read_text())
        assert on_disk["pkg-b"]["release"] == 9  # untouched

    def test_only_targeted_package_changes_on_disk(self, packages_yaml, _run):
        """Bumping one package's release leaves every other field byte-for-byte."""
        from lib.cache import compute_input_hashes

        packages = {
            "pkg-a": {
                "version": "1.0",
                "release": 1,
                "license": "GPLv3",
                "summary": "A",
                "description": "A",
                "url": "https://example.com/a",
            },
            "pkg-b": {
                "version": "2.0",
                "release": 9,
                "license": "GPLv3",
                "summary": "B",
                "description": "B",
                "url": "https://example.com/b",
            },
        }
        _seed("pkg-a", "spec", hashes={"content": "old_hash_a", "package_version": "1.0"})
        _seed(
            "pkg-b",
            "spec",
            hashes=compute_input_hashes("pkg-b", packages["pkg-b"], packages),
        )

        updates = _run(packages)
        assert updates == {"pkg-a": 2}

        on_disk = yaml.safe_load(packages_yaml.read_text())
        assert on_disk["pkg-b"] == packages["pkg-b"]

    def test_target_missing_from_file_raises(self, packages_yaml):
        """A release update for a package absent from the file raises loudly.

        Previously this was a silent no-op reported as a successful update.
        """
        packages = {
            "ghost-pkg": {
                "version": "1.0",
                "release": 1,
                "license": "GPLv3",
                "summary": "Ghost",
                "description": "Ghost",
                "url": "https://example.com/ghost",
            }
        }
        _seed("ghost-pkg", "spec", hashes={"content": "old_hash", "package_version": "1.0"})

        # update_package_releases() is asked (via the `packages` arg) to bump
        # a package the on-disk file doesn't have at all.
        packages_yaml.write_text("---\n" + dump_yaml_pretty({}))

        with pytest.raises(KeyError, match="ghost-pkg"):
            update_package_releases(packages, TARGET)

    def test_on_disk_value_matches_return_value(self, packages_yaml, _run):
        """The returned `updates` dict reflects what actually landed on disk."""
        packages = {
            "test-pkg": {
                "version": "1.0",
                "release": 1,
                "license": "GPLv3",
                "summary": "Test",
                "description": "Test",
                "url": "https://example.com",
            }
        }
        _seed("test-pkg", "spec", hashes={"content": "old_hash", "package_version": "1.0"})

        updates = _run(packages)
        on_disk = yaml.safe_load(packages_yaml.read_text())
        assert on_disk["test-pkg"]["release"] == updates["test-pkg"]

    def test_release_lock_package_untouched_on_disk(self, packages_yaml, _run):
        """release_lock package is skipped, not just absent from `updates`."""
        packages = {
            "locked-pkg": {
                "version": "1.0",
                "release": 5,
                "release_lock": True,
                "license": "GPLv3",
                "summary": "Test",
                "description": "Test pkg (modified)",
                "url": "https://example.com",
            }
        }
        _seed("locked-pkg", "spec", hashes={"content": "old_hash", "package_version": "1.0"})

        updates = _run(packages)
        assert updates == {}

        on_disk = yaml.safe_load(packages_yaml.read_text())
        assert on_disk["locked-pkg"]["release"] == 5

    def test_document_start_survives_a_write(self, packages_yaml, _run):
        """The leading `---` document marker is preserved, not stripped."""
        packages = {
            "test-pkg": {
                "version": "1.0",
                "release": 1,
                "license": "GPLv3",
                "summary": "Test",
                "description": "Test",
                "url": "https://example.com",
            }
        }
        _seed("test-pkg", "spec", hashes={"content": "old_hash", "package_version": "1.0"})

        _run(packages)
        assert packages_yaml.read_text().startswith("---\n")
