"""Unit tests for release autoincrement and autoreset logic."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib.yaml_utils import update_package_releases


class TestUpdatePackageReleases:
    """Test release auto-increment and autoreset logic."""

    def test_first_run_no_stored_hash(self):
        """First run (no stored hash) → needs_rebuild=True, release = 1."""
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
        build_status = {"stages": {"spec": {}}}

        updates = update_package_releases(packages, build_status)
        # First run, no stored content_hash → all packages need rebuild
        # But release is already 1, so no update needed
        assert updates == {}

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

        build_status = {
            "stages": {
                "spec": {
                    "test-pkg": {
                        "hashes": {
                            "content": actual_content,  # <- matches computed
                            "package_version": "1.0",
                        }
                    }
                }
            }
        }

        updates = update_package_releases(packages, build_status)
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
        build_status = {
            "stages": {
                "spec": {
                    "test-pkg": {
                        "hashes": {
                            "content": "old_hash",  # <- doesn't match computed
                            "package_version": "1.0",
                        }
                    }
                }
            }
        }

        updates = update_package_releases(packages, build_status)
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
        build_status = {
            "stages": {
                "spec": {
                    "test-pkg": {
                        "hashes": {
                            "content": "old_hash",
                            "package_version": "1.0",  # <- version was 1.0
                        }
                    }
                }
            }
        }

        updates = update_package_releases(packages, build_status)
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
        build_status = {
            "stages": {
                "spec": {
                    "test-pkg": {
                        "hashes": {
                            "content": "current_hash",
                            "package_version": "1.0",  # <- same version
                        }
                    }
                }
            }
        }

        updates = update_package_releases(packages, build_status)
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
        build_status = {
            "stages": {
                "spec": {
                    "test-pkg": {
                        "hashes": {
                            "content": "old_hash",  # <- differs → needs rebuild
                            "package_version": "1.0",
                        }
                    }
                }
            }
        }

        updates = update_package_releases(packages, build_status)
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
        build_status = {
            "stages": {
                "spec": {
                    "test-pkg": {
                        "hashes": {
                            "content": "current_hash",
                            "package_version": "1.0",
                        },
                        "force_run": True,  # <- operator forced rebuild
                    }
                }
            }
        }

        updates = update_package_releases(packages, build_status)
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
        build_status = {
            "stages": {
                "spec": {
                    "test-pkg": {
                        "hashes": {
                            "content": "current_hash",
                            "package_version": "1.0",
                        }
                    }
                },
                "mock": {
                    "test-pkg": {
                        "force_run": True,  # <- forced in downstream stage
                    }
                },
            }
        }

        updates = update_package_releases(packages, build_status)
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
        build_status = {
            "stages": {
                "spec": {
                    "pkg-a": {
                        "hashes": {
                            "content": "old_hash_a",  # <- A's content changed
                            "package_version": "1.0",
                        }
                    },
                    "pkg-b": {
                        "hashes": {
                            "content": "current_hash_b",
                            "package_version": "1.0",
                        }
                    },
                }
            }
        }

        updates = update_package_releases(packages, build_status)
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
        build_status = {
            "stages": {
                "spec": {
                    "pkg-a": {
                        "hashes": {
                            "content": "old_hash_a",  # <- A changed
                            "package_version": "1.0",
                        }
                    },
                    "pkg-b": {
                        "hashes": {
                            "content": "current_hash_b",
                            "package_version": "1.0",
                        }
                    },
                    "pkg-c": {
                        "hashes": {
                            "content": "current_hash_c",
                            "package_version": "1.0",
                        }
                    },
                }
            }
        }

        updates = update_package_releases(packages, build_status)
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

        build_status = {
            "stages": {
                "spec": {
                    "pkg-a": {
                        "hashes": {
                            "content": "old_hash_a",  # <- differs from computed
                            "package_version": "1.0",
                        }
                    },
                    "pkg-b": {
                        "hashes": {
                            "content": _content_hash(pkg_b),  # <- matches
                            "package_version": "1.0",
                        }
                    },
                }
            }
        }

        updates = update_package_releases(packages, build_status)
        assert "pkg-a" in updates
        assert "pkg-b" not in updates  # B not affected

    def test_no_stored_entry_for_dep(self):
        """dep missing from build_status → treated as first-run, cascades."""
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

        build_status = {
            "stages": {
                "spec": {
                    # pkg-a not in build_status (first run for A)
                    "pkg-b": {
                        "hashes": {
                            "content": _content_hash(pkg_b),
                            "package_version": "1.0",
                        }
                    }
                }
            }
        }

        updates = update_package_releases(packages, build_status)
        # pkg-a: first run, needs_rebuild=True, version_changed=True → new_release=1
        # But current release is already 1, so no update needed
        assert "pkg-a" not in updates
        # pkg-b: cascaded from pkg-a, release 1 + 1 = 2
        assert "pkg-b" in updates
        assert updates["pkg-b"] == 2  # B cascaded (1 + 1)

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

        build_status = {
            "stages": {
                "spec": {
                    "dep-1": {
                        "hashes": {
                            "content": "old_hash_dep1",  # <- differs from computed
                            "package_version": "1.0",
                        }
                    },
                    "dep-2": {
                        "hashes": {
                            "content": _content_hash(dep2),  # <- matches
                            "package_version": "1.0",
                        }
                    },
                    "pkg": {
                        "hashes": {
                            "content": _content_hash(pkg),  # <- matches
                            "package_version": "1.0",
                        }
                    },
                }
            }
        }

        updates = update_package_releases(packages, build_status)
        assert updates["dep-1"] == 2
        assert "dep-2" not in updates
        assert updates["pkg"] == 6  # cascaded from dep-1 (5 + 1)

    def test_release_lock_prevents_auto_increment(self):
        """release_lock: true → package skipped, release not updated."""
        from lib.cache import _content_hash

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

        build_status = {
            "stages": {
                "spec": {
                    "test-pkg": {
                        "hashes": {
                            "content": "old_hash",  # <- differs from computed
                            "package_version": "1.0",
                        }
                    }
                }
            }
        }

        updates = update_package_releases(packages, build_status)
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

        build_status = {
            "stages": {
                "spec": {
                    "test-pkg": {
                        "hashes": {
                            "content": "old_hash",
                            "package_version": "1.0",
                        }
                    }
                }
            }
        }

        updates = update_package_releases(packages, build_status)
        # release_lock=True → skipped even though version changed
        assert updates == {}
