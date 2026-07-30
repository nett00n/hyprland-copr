"""Unit tests for release autoincrement and autoreset logic."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib import build_db, paths
from lib.yaml_utils import update_package_releases

TARGET = "fedora-44-x86_64"


@pytest.fixture(autouse=True)
def build_db_path(tmp_path, monkeypatch):
    """Point lib.paths.BUILD_DB at a fresh tmp file and close the cached connection after."""
    db_path = tmp_path / "build-report.db"
    monkeypatch.setattr(paths, "BUILD_DB", db_path)
    yield db_path
    build_db.close()


def _seed(pkg: str, stage: str, hashes: dict | None = None, force_run: int = 0, state: str = "success") -> None:
    """Seed a stage row, optionally with hashes (which requires state=success)."""
    run_id = build_db.start_run(TARGET, "fedora", "44", "x86_64")
    build_db.set_stage(pkg, stage, TARGET, run_id, state, force_run=force_run)
    if hashes is not None:
        build_db.finalize_stage(pkg, stage, TARGET, started_at=1, hashes=hashes)


class TestUpdatePackageReleases:
    """Test release auto-increment and autoreset logic."""

    def test_first_run_no_stored_hash(self):
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

        updates = update_package_releases(packages, TARGET)
        # First run, no stored content_hash → package needs rebuild
        # Release must be bumped: 1 → 2
        assert updates == {"test-pkg": 2}

    def test_content_unchanged_no_force(self):
        """Content unchanged, no force_run → no update."""
        from lib.cache import _content_hash

        pkg_dict = {
            "version": "1.0",
            "release": 2,
            "license": "GPLv3",
            "summary": "Test",
            "description": "Test pkg",
            "url": "https://example.com",
        }
        packages = {"test-pkg": pkg_dict}

        # Compute the actual content hash for this package
        actual_content = _content_hash(pkg_dict)

        _seed(
            "test-pkg",
            "spec",
            hashes={"content": actual_content, "package_version": "1.0"},  # <- matches computed
        )

        updates = update_package_releases(packages, TARGET)
        # Content unchanged, no cascade → no update
        assert updates == {}

    def test_content_changed_same_version(self):
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

        updates = update_package_releases(packages, TARGET)
        assert "test-pkg" in updates
        assert updates["test-pkg"] == 3  # 2 + 1

    def test_content_changed_version_changed(self):
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

        updates = update_package_releases(packages, TARGET)
        assert "test-pkg" in updates
        assert updates["test-pkg"] == 1  # Reset on version change

    def test_release_is_zero(self):
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

        updates = update_package_releases(packages, TARGET)
        assert "test-pkg" in updates
        assert updates["test-pkg"] == 1

    def test_release_is_autorelease_string(self):
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

        updates = update_package_releases(packages, TARGET)
        assert "test-pkg" in updates
        assert updates["test-pkg"] == 1  # Fallback

    def test_force_run_in_spec_stage(self):
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

        updates = update_package_releases(packages, TARGET)
        assert "test-pkg" in updates
        assert updates["test-pkg"] == 3  # 2 + 1

    def test_force_run_in_mock_stage(self):
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

        updates = update_package_releases(packages, TARGET)
        assert "test-pkg" in updates
        assert updates["test-pkg"] == 3  # 2 + 1

    def test_dep_rebuild_cascades(self):
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

        updates = update_package_releases(packages, TARGET)
        assert "pkg-a" in updates
        assert updates["pkg-a"] == 2  # A's content changed
        assert "pkg-b" in updates
        assert updates["pkg-b"] == 3  # B cascaded (2 + 1)

    def test_dep_chain_cascade(self):
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

        updates = update_package_releases(packages, TARGET)
        assert updates["pkg-a"] == 2  # A changed
        assert updates["pkg-b"] == 2  # B cascaded
        assert updates["pkg-c"] == 2  # C cascaded

    def test_independent_pkg_not_cascaded(self):
        """pkg A rebuilt, pkg B has no depends_on A → B release unchanged."""
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
            hashes={"content": _content_hash(pkg_b), "package_version": "1.0"},  # <- matches
        )

        updates = update_package_releases(packages, TARGET)
        assert "pkg-a" in updates
        assert "pkg-b" not in updates  # B not affected

    def test_no_stored_entry_for_dep(self):
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

        updates = update_package_releases(packages, TARGET)
        # pkg-a: first run, no stored entry → needs_rebuild=True → release 1 + 1 = 2
        assert "pkg-a" in updates
        assert updates["pkg-a"] == 2
        # pkg-b: cascaded from pkg-a rebuild → needs_rebuild=True → release 1 + 1 = 2
        assert "pkg-b" in updates
        assert updates["pkg-b"] == 2

    def test_multiple_deps_one_changed(self):
        """pkg has multiple deps, only one changed → pkg release increments once."""
        from lib.cache import _content_hash

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
            hashes={"content": _content_hash(dep2), "package_version": "1.0"},  # <- matches
        )
        _seed("pkg", "spec", hashes={"content": _content_hash(pkg), "package_version": "1.0"})

        updates = update_package_releases(packages, TARGET)
        assert updates["dep-1"] == 2
        assert "dep-2" not in updates
        assert updates["pkg"] == 6  # cascaded from dep-1 (5 + 1)

    def test_release_lock_prevents_auto_increment(self):
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

        updates = update_package_releases(packages, TARGET)
        # release_lock=True → skipped, no update
        assert updates == {}

    def test_release_lock_with_version_change(self):
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

        updates = update_package_releases(packages, TARGET)
        # release_lock=True → skipped even though version changed
        assert updates == {}

    def test_dependency_release_change_does_not_cascade(self):
        """Dependency release change alone does NOT cascade to dependents.

        This verifies the fix for "metadata is still old" issue where release
        changes in dependencies would incorrectly trigger dependent package rebuilds.

        The dependency hash (used to detect content changes) excludes release,
        so only actual content changes cascade, not release-only changes.
        """
        from lib.cache import _package_config_hash, _content_hash

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
        dep_hash_1 = _package_config_hash(dep)

        # Now bump dependency release to 2
        dep_bumped = dict(dep)
        dep_bumped["release"] = 2
        all_packages_2 = {"dep": dep_bumped, "pkg": pkg}
        dep_hash_2 = _package_config_hash(dep_bumped)

        # Verify: dependency hash should NOT change with release-only change
        assert dep_hash_1 == dep_hash_2, (
            "Release-only change should not affect dependency hash "
            "(prevents unnecessary cascades)"
        )
