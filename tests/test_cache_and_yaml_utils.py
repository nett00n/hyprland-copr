"""Unit tests for scripts/lib/cache.py and lib/yaml_utils.py"""

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.cache import hashes_match, _sha256, _package_config_hash, _dependencies_hashes, _patches_hashes
from lib.yaml_utils import (
    find_package_name,
    filter_packages,
    skip_packages,
    apply_os_overrides,
    load_packages_yaml,
    load_repo_yaml,
    load_groups_yaml,
    dump_yaml_pretty,
    save_build_status,
    pop_build_stages,
    now_epoch,
    init_stage,
    write_yaml_preserving_comments,
)


class TestHashesMatch:
    """Test hash comparison for cache validation."""

    def test_matching_hashes(self):
        """Identical hashes match."""
        stored = {"hashes": {"a": "hash1", "b": "hash2"}}
        new = {"a": "hash1", "b": "hash2"}
        assert hashes_match(stored, new) is True

    def test_mismatched_hashes(self):
        """Different hashes don't match."""
        stored = {"hashes": {"a": "hash1"}}
        new = {"a": "hash2"}
        assert hashes_match(stored, new) is False

    def test_missing_stored_hashes(self):
        """Missing stored hashes returns False."""
        stored = {}
        new = {"a": "hash1"}
        assert hashes_match(stored, new) is False

    def test_missing_new_hash_key(self):
        """Extra key in stored hashes returns False."""
        stored = {"hashes": {"a": "hash1", "b": "hash2"}}
        new = {"a": "hash1"}
        assert hashes_match(stored, new) is False

    def test_extra_new_hash_key(self):
        """Extra key in new hashes returns False."""
        stored = {"hashes": {"a": "hash1"}}
        new = {"a": "hash1", "b": "hash2"}
        assert hashes_match(stored, new) is False

    def test_empty_hashes(self):
        """Both empty return False (falsy)."""
        stored = {"hashes": {}}
        new = {}
        # empty dict is falsy, so bool({}) is False
        assert hashes_match(stored, new) is False

    def test_none_stored_hashes(self):
        """None in stored returns False."""
        stored = {"hashes": None}
        new = {}
        assert hashes_match(stored, new) is False


class TestFindPackageName:
    """Test case-insensitive package name lookup."""

    def test_exact_match(self):
        """Exact case match returns the key."""
        packages = {"foo": {}, "Bar": {}}
        assert find_package_name(packages, "foo") == "foo"

    def test_case_insensitive_match(self):
        """Case-insensitive match returns correct case."""
        packages = {"MyPackage": {}}
        assert find_package_name(packages, "mypackage") == "MyPackage"

    def test_no_match_returns_none(self):
        """Non-existent package returns None."""
        packages = {"foo": {}}
        assert find_package_name(packages, "bar") is None

    def test_empty_packages_dict(self):
        """Empty dict returns None."""
        packages = {}
        assert find_package_name(packages, "foo") is None

    def test_empty_query_returns_none(self):
        """Empty query returns None."""
        packages = {"foo": {}}
        assert find_package_name(packages, "") is None

    def test_mixed_case_names(self):
        """Multiple packages with different cases."""
        packages = {"Hyprland": {}, "hyprwire": {}, "MyPackage": {}}
        assert find_package_name(packages, "HYPRLAND") == "Hyprland"
        assert find_package_name(packages, "hyprWire") == "hyprwire"


class TestFilterPackages:
    """Test package filtering by PACKAGE env var."""

    def test_empty_env_returns_all(self):
        """Empty PACKAGE env returns all packages."""
        packages = {"foo": {"data": 1}, "bar": {"data": 2}}
        result = filter_packages(packages, "")
        assert result == packages

    def test_single_package_name(self):
        """Single package name filters to that package."""
        packages = {"foo": {"data": 1}, "bar": {"data": 2}}
        result = filter_packages(packages, "foo")
        assert result == {"foo": {"data": 1}}

    def test_comma_separated_list(self):
        """Comma-separated list filters multiple packages."""
        packages = {"a": {}, "b": {}, "c": {}}
        result = filter_packages(packages, "a,c")
        assert set(result.keys()) == {"a", "c"}

    def test_case_insensitive_matching(self):
        """Package names matched case-insensitively."""
        packages = {"MyPackage": {"data": 1}, "Other": {"data": 2}}
        result = filter_packages(packages, "mypackage")
        assert result == {"MyPackage": {"data": 1}}

    def test_whitespace_stripped_from_names(self):
        """Whitespace around names is stripped."""
        packages = {"foo": {}, "bar": {}}
        result = filter_packages(packages, " foo , bar ")
        assert set(result.keys()) == {"foo", "bar"}

    def test_unknown_package_exits(self, monkeypatch):
        """Unknown package name causes sys.exit."""
        packages = {"foo": {}}
        with pytest.raises(SystemExit):
            filter_packages(packages, "nonexistent")

    def test_mixed_known_unknown_exits(self, monkeypatch):
        """Mix of known and unknown packages causes exit."""
        packages = {"foo": {}}
        with pytest.raises(SystemExit):
            filter_packages(packages, "foo,unknown")


class TestSkipPackages:
    """Test package exclusion by SKIP_PACKAGES env var."""

    def test_empty_skip_returns_all(self):
        """Empty SKIP_PACKAGES returns all packages."""
        packages = {"a": {"data": 1}, "b": {"data": 2}}
        result = skip_packages(packages, "")
        assert result == packages

    def test_skip_single_package(self):
        """Skip removes specified package."""
        packages = {"a": {"data": 1}, "b": {"data": 2}}
        result = skip_packages(packages, "a")
        assert result == {"b": {"data": 2}}

    def test_skip_comma_separated(self):
        """Skip multiple comma-separated packages."""
        packages = {"a": {}, "b": {}, "c": {}}
        result = skip_packages(packages, "a,c")
        assert result == {"b": {}}

    def test_skip_case_insensitive(self):
        """Skip matching is case-insensitive."""
        packages = {"MyPackage": {"data": 1}, "Other": {"data": 2}}
        result = skip_packages(packages, "mypackage")
        assert result == {"Other": {"data": 2}}

    def test_skip_nonexistent_package(self):
        """Skip nonexistent package doesn't error."""
        packages = {"a": {}}
        result = skip_packages(packages, "nonexistent")
        assert result == packages

    def test_skip_whitespace_stripped(self):
        """Whitespace in skip list is stripped."""
        packages = {"a": {}, "b": {}, "c": {}}
        result = skip_packages(packages, " a , b ")
        assert result == {"c": {}}


class TestApplyOsOverrides:
    """Test Fedora version-specific overrides."""

    def test_no_fedora_block_returns_original(self):
        """No fedora block returns package unchanged."""
        pkg = {"version": "1.0", "name": "foo"}
        result = apply_os_overrides(pkg, "43")
        assert result == {"version": "1.0", "name": "foo"}

    def test_matching_version_override(self):
        """Matching fedora version applies override."""
        pkg = {
            "version": "1.0",
            "build_requires": ["a"],
            "fedora": {
                "43": {
                    "build_requires": ["b"],
                }
            }
        }
        result = apply_os_overrides(pkg, "43")
        assert result["build_requires"] == ["b"]
        assert "fedora" not in result

    def test_non_matching_version_no_override(self):
        """Non-matching fedora version no override applied."""
        pkg = {
            "version": "1.0",
            "build_requires": ["a"],
            "fedora": {
                "44": {
                    "build_requires": ["b"],
                }
            }
        }
        result = apply_os_overrides(pkg, "43")
        assert result["build_requires"] == ["a"]

    def test_rawhide_override(self):
        """rawhide fedora version override (only specific fields are merged)."""
        pkg = {
            "version": "1.0",
            "build_requires": ["a"],
            "fedora": {
                "rawhide": {
                    "build_requires": ["b"],
                }
            }
        }
        result = apply_os_overrides(pkg, "rawhide")
        # Only specific fields (build_requires, requires, build.*, source.patches) are merged
        assert result["build_requires"] == ["b"]
        assert "fedora" not in result

    def test_integer_fedora_version_match(self):
        """Integer fedora versions work (only specific fields merged)."""
        pkg = {
            "name": "pkg",
            "build_requires": ["base"],
            "fedora": {
                44: {
                    "build_requires": ["override"],
                }
            }
        }
        result = apply_os_overrides(pkg, "44")
        assert result["build_requires"] == ["override"]
        assert result["name"] == "pkg"  # Non-override fields preserved

    def test_skip_flag_set(self):
        """Skip flag in override sets _skip."""
        pkg = {
            "version": "1.0",
            "fedora": {
                "43": {
                    "skip": True,
                }
            }
        }
        result = apply_os_overrides(pkg, "43")
        assert result.get("_skip") is True

    def test_fedora_block_removed_from_result(self):
        """fedora block is removed from result."""
        pkg = {
            "version": "1.0",
            "fedora": {
                "43": {}
            }
        }
        result = apply_os_overrides(pkg, "43")
        assert "fedora" not in result

    def test_nested_override_source_patches(self):
        """Nested source/patches override."""
        pkg = {
            "source": {
                "patches": ["a.patch"],
            },
            "fedora": {
                "44": {
                    "source": {
                        "patches": ["b.patch"],
                    }
                }
            }
        }
        result = apply_os_overrides(pkg, "44")
        # Deep merge behavior depends on implementation
        # Assuming shallow merge of source dict
        assert "patches" in result.get("source", {})

    def test_multiple_fedora_overrides_exact_match_wins(self):
        """Exact version match preferred over non-match (only specific fields merged)."""
        pkg = {
            "name": "test",
            "build_requires": ["base"],
            "fedora": {
                "43": {"build_requires": ["test-fc43"]},
                "44": {"build_requires": ["test-fc44"]},
            }
        }
        result = apply_os_overrides(pkg, "43")
        assert result["build_requires"] == ["test-fc43"]
        assert result["name"] == "test"  # name not in override list


class TestLoadBuildStatus:
    """Test load_build_status normalization."""

    def test_missing_stages_key_normalized(self, tmp_path, monkeypatch):
        """load_build_status should normalize missing 'stages' key."""
        from lib.yaml_utils import load_build_status
        from lib import paths

        monkeypatch.setattr(paths, "BUILD_STATUS_YAML", tmp_path / "build-report.yaml")

        # Write a build-report.yaml with missing stages key
        report_file = tmp_path / "build-report.yaml"
        report_file.write_text("{}")

        status = load_build_status(report_file)
        # Should have normalized structure with stages key
        assert "stages" in status

    def test_empty_file_normalized(self, tmp_path, monkeypatch):
        """load_build_status should normalize empty YAML file."""
        from lib.yaml_utils import load_build_status
        from lib import paths

        monkeypatch.setattr(paths, "BUILD_STATUS_YAML", tmp_path / "build-report.yaml")

        report_file = tmp_path / "build-report.yaml"
        report_file.write_text("")

        status = load_build_status(report_file)
        # Empty file should use default structure
        assert "stages" in status

    def test_non_existent_file_default_structure(self, tmp_path, monkeypatch):
        """load_build_status should return default structure if file missing."""
        from lib.yaml_utils import load_build_status
        from lib import paths

        monkeypatch.setattr(paths, "BUILD_STATUS_YAML", tmp_path / "build-report.yaml")

        report_file = tmp_path / "build-report.yaml"

        status = load_build_status(report_file)
        # Non-existent file should use default structure
        assert "stages" in status
        assert isinstance(status["stages"], dict)


class TestLoadPackagesYaml:
    """Test load_packages_yaml function."""

    def test_loads_valid_yaml(self, tmp_path, monkeypatch):
        """Should load valid packages.yaml."""
        from lib import paths

        yaml_file = tmp_path / "packages.yaml"
        yaml_file.write_text("foo:\n  version: '1.0'\nbar:\n  version: '2.0'")
        monkeypatch.setattr(paths, "PACKAGES_YAML", yaml_file)

        result = load_packages_yaml(yaml_file)
        assert result["foo"]["version"] == "1.0"
        assert result["bar"]["version"] == "2.0"

    def test_returns_empty_dict_on_none_content(self, tmp_path, monkeypatch):
        """Should return empty dict if YAML is None/empty."""
        from lib import paths

        yaml_file = tmp_path / "packages.yaml"
        yaml_file.write_text("")
        monkeypatch.setattr(paths, "PACKAGES_YAML", yaml_file)

        result = load_packages_yaml(yaml_file)
        assert result == {}

    def test_exits_on_missing_file(self, tmp_path, monkeypatch):
        """Should exit if file doesn't exist."""
        from lib import paths

        yaml_file = tmp_path / "nonexistent.yaml"
        monkeypatch.setattr(paths, "PACKAGES_YAML", yaml_file)

        with pytest.raises(SystemExit):
            load_packages_yaml(yaml_file)

    def test_exits_on_invalid_yaml(self, tmp_path, monkeypatch):
        """Should exit on malformed YAML."""
        from lib import paths

        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("{ invalid: yaml: content:")
        monkeypatch.setattr(paths, "PACKAGES_YAML", yaml_file)

        with pytest.raises(SystemExit):
            load_packages_yaml(yaml_file)


class TestLoadRepoYaml:
    """Test load_repo_yaml function."""

    def test_loads_valid_yaml(self, tmp_path, monkeypatch):
        """Should load valid repo.yaml."""
        from lib import paths

        yaml_file = tmp_path / "repo.yaml"
        yaml_file.write_text("name: 'my-repo'")
        monkeypatch.setattr(paths, "REPO_YAML", yaml_file)

        result = load_repo_yaml(yaml_file)
        assert result["name"] == "my-repo"

    def test_returns_empty_dict_if_missing(self, tmp_path, monkeypatch):
        """Should return empty dict if file missing."""
        from lib import paths

        yaml_file = tmp_path / "nonexistent.yaml"
        monkeypatch.setattr(paths, "REPO_YAML", yaml_file)

        result = load_repo_yaml(yaml_file)
        assert result == {}

    def test_exits_on_invalid_yaml(self, tmp_path, monkeypatch):
        """Should exit on malformed YAML."""
        from lib import paths

        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("{ invalid: yaml:")
        monkeypatch.setattr(paths, "REPO_YAML", yaml_file)

        with pytest.raises(SystemExit):
            load_repo_yaml(yaml_file)


class TestLoadGroupsYaml:
    """Test load_groups_yaml function."""

    def test_loads_valid_yaml(self, tmp_path, monkeypatch):
        """Should load valid groups.yaml."""
        from lib import paths

        yaml_file = tmp_path / "groups.yaml"
        yaml_file.write_text("hyprland:\n  - pkg1\n  - pkg2")
        monkeypatch.setattr(paths, "GROUPS_YAML", yaml_file)

        result = load_groups_yaml(yaml_file)
        assert "hyprland" in result

    def test_returns_empty_dict_if_missing(self, tmp_path, monkeypatch):
        """Should return empty dict if file missing."""
        from lib import paths

        yaml_file = tmp_path / "nonexistent.yaml"
        monkeypatch.setattr(paths, "GROUPS_YAML", yaml_file)

        result = load_groups_yaml(yaml_file)
        assert result == {}


class TestPopBuildStages:
    """Test pop_build_stages function."""

    def test_handles_missing_packages(self, tmp_path, monkeypatch):
        """Should handle packages not in report."""
        from lib import paths

        status_file = tmp_path / "build-report.yaml"
        monkeypatch.setattr(paths, "BUILD_STATUS_YAML", status_file)

        initial = {"stages": {"mock": {}, "copr": {}}}
        save_build_status(initial, status_file)

        affected = pop_build_stages(["nonexistent"], ("mock", "copr"))
        assert affected == []


class TestNowEpoch:
    """Test now_epoch function."""

    def test_returns_int(self):
        """Should return integer timestamp."""
        result = now_epoch()
        assert isinstance(result, int)

    def test_returns_recent_timestamp(self):
        """Should return a recent (current) timestamp."""
        import time

        before = int(time.time())
        result = now_epoch()
        after = int(time.time())
        assert before <= result <= after + 1


class TestInitStage:
    """Test init_stage function."""

    def test_returns_packages_and_status(self, tmp_path, monkeypatch, caplog):
        """Should return tuple of (packages, build_status)."""
        from lib import paths

        # Setup mock packages.yaml
        packages_file = tmp_path / "packages.yaml"
        packages_file.write_text("pkg1:\n  version: '1.0'")
        monkeypatch.setattr(paths, "PACKAGES_YAML", packages_file)

        status_file = tmp_path / "build-report.yaml"
        monkeypatch.setattr(paths, "BUILD_STATUS_YAML", status_file)
        monkeypatch.setattr(paths, "BUILD_LOG_DIR", tmp_path / "logs")

        # Clear env vars
        monkeypatch.delenv("PACKAGE", raising=False)
        monkeypatch.delenv("SKIP_PACKAGES", raising=False)
        monkeypatch.delenv("PROCEED_BUILD", raising=False)

        result = init_stage("spec", include_all=False)
        assert isinstance(result, tuple)
        assert len(result) == 2
        packages, build_status = result
        assert isinstance(packages, dict)
        assert isinstance(build_status, dict)
        assert "stages" in build_status

    def test_clears_stage_if_not_resuming(self, tmp_path, monkeypatch):
        """Should clear stage data if not resuming (PROCEED_BUILD != true)."""
        from lib import paths

        packages_file = tmp_path / "packages.yaml"
        packages_file.write_text("pkg1:\n  version: '1.0'")
        monkeypatch.setattr(paths, "PACKAGES_YAML", packages_file)

        status_file = tmp_path / "build-report.yaml"
        monkeypatch.setattr(paths, "BUILD_STATUS_YAML", status_file)
        monkeypatch.setattr(paths, "BUILD_LOG_DIR", tmp_path / "logs")

        # Pre-populate build status
        pre_status = {"stages": {"spec": {"pkg1": {"state": "success"}}}}
        save_build_status(pre_status, status_file)

        monkeypatch.delenv("PACKAGE", raising=False)
        monkeypatch.delenv("SKIP_PACKAGES", raising=False)
        monkeypatch.setenv("PROCEED_BUILD", "false")

        packages, build_status = init_stage("spec")

        # Stage should be cleared
        assert build_status["stages"]["spec"] == {}


class TestWriteYamlPreservingComments:
    """Test write_yaml_preserving_comments function."""

    def test_updates_version(self, tmp_path):
        """Should update package versions."""
        pkg_file = tmp_path / "packages.yaml"
        pkg_file.write_text("mypackage:\n  url: 'https://github.com/foo/bar'\n  version: '1.0'")

        url_to_latest = {"https://github.com/foo/bar": "2.0"}
        changed = write_yaml_preserving_comments(pkg_file, url_to_latest)

        assert "mypackage" in changed
        assert changed["mypackage"] == ("1.0", "2.0")

        # Verify file was updated
        updated_content = pkg_file.read_text()
        assert "2.0" in updated_content

    def test_ignores_unchanged_versions(self, tmp_path):
        """Should not modify packages with same version."""
        pkg_file = tmp_path / "packages.yaml"
        pkg_file.write_text("mypackage:\n  url: 'https://github.com/foo/bar'\n  version: '1.0'")

        url_to_latest = {"https://github.com/foo/bar": "1.0"}
        changed = write_yaml_preserving_comments(pkg_file, url_to_latest)

        assert changed == {}

    def test_handles_commit_info(self, tmp_path):
        """Should handle commit-based versions."""
        pkg_file = tmp_path / "packages.yaml"
        pkg_file.write_text(
            "mypackage:\n  url: 'https://github.com/foo/bar'\n  version: '1.0'\n  source:\n    commit: {}\n  auto_update:\n    release_type: latest-commit"
        )

        url_to_commit_info = {
            "https://github.com/foo/bar": ("abc123full", "abc123", "20250115", "1.0")
        }
        changed = write_yaml_preserving_comments(
            pkg_file, {}, url_to_commit_info
        )

        # Should update with commit version
        assert "mypackage" in changed

    def test_returns_change_dict(self, tmp_path):
        """Should return dict of changed packages."""
        pkg_file = tmp_path / "packages.yaml"
        pkg_file.write_text("pkg1:\n  url: 'https://a'\n  version: '1.0'\npkg2:\n  url: 'https://b'\n  version: '2.0'")

        url_to_latest = {"https://a": "2.0", "https://b": "2.0"}
        changed = write_yaml_preserving_comments(pkg_file, url_to_latest)

        assert len(changed) == 1  # Only pkg1 changed
        assert "pkg1" in changed


class TestCacheHelpers:
    """Test cache helper functions."""

    def test_sha256_deterministic(self):
        """_sha256 should produce consistent hashes."""
        data = b"test content"
        hash1 = _sha256(data)
        hash2 = _sha256(data)
        assert hash1 == hash2

    def test_sha256_differs_for_different_data(self):
        """_sha256 should differ for different content."""
        hash1 = _sha256(b"content1")
        hash2 = _sha256(b"content2")
        assert hash1 != hash2

    def test_package_config_hash_deterministic(self):
        """_package_config_hash should be deterministic."""
        meta = {"build_requires": ["gcc"], "requires": ["glibc"]}
        hash1 = _package_config_hash(meta)
        hash2 = _package_config_hash(meta)
        assert hash1 == hash2

    def test_package_config_hash_key_order_independent(self):
        """_package_config_hash should be independent of key order."""
        meta1 = {"build_requires": ["gcc"], "requires": ["glibc"]}
        meta2 = {"requires": ["glibc"], "build_requires": ["gcc"]}
        # Both dicts are equivalent, so hashes should be same
        hash1 = _package_config_hash(meta1)
        hash2 = _package_config_hash(meta2)
        # Should normalize before hashing
        assert hash1 == hash2


    def test_patches_hashes(self, tmp_path, monkeypatch):
        """_patches_hashes should hash patch files."""
        from lib import paths

        monkeypatch.setattr(paths, "ROOT", tmp_path)

        # Create a patch file
        pkg_dir = tmp_path / "packages" / "mypkg"
        pkg_dir.mkdir(parents=True)
        patch_file = pkg_dir / "fix.patch"
        patch_file.write_text("patch content")

        meta = {"source": {"patches": ["fix.patch"]}}
        result = _patches_hashes("mypkg", meta)

        # Should contain hashes for patches
        assert len(result) > 0


class TestWriteYamlPreservingCommentsRelease:
    """Test release field handling in write_yaml_preserving_comments."""

    def test_version_change_resets_release_to_zero(self, tmp_path):
        """When version changes, release field is set to 0."""
        yaml_file = tmp_path / "packages.yaml"
        yaml_file.write_text("""
test-pkg:
  version: "1.0"
  release: 3
  url: https://example.com/test
  license: GPLv3
  summary: Test
  description: Test pkg
""")

        url_to_latest = {"https://example.com/test": "2.0"}
        write_yaml_preserving_comments(yaml_file, url_to_latest, None)

        content = yaml_file.read_text()
        assert "version: '2.0'" in content or 'version: "2.0"' in content
        assert "release: 0" in content

    def test_no_version_change_preserves_release(self, tmp_path):
        """When version unchanged, release stays the same."""
        yaml_file = tmp_path / "packages.yaml"
        yaml_file.write_text("""
test-pkg:
  version: "1.0"
  release: 3
  url: https://example.com/test
  license: GPLv3
  summary: Test
  description: Test pkg
""")

        url_to_latest = {"https://example.com/test": "1.0"}
        write_yaml_preserving_comments(yaml_file, url_to_latest, None)

        content = yaml_file.read_text()
        assert "release: 3" in content

    def test_commit_version_change_resets_release(self, tmp_path):
        """When commit version changes, release is set to 0."""
        yaml_file = tmp_path / "packages.yaml"
        yaml_file.write_text("""
test-pkg:
  version: "0^20260101gitabc123"
  release: 2
  url: https://example.com/test
  license: GPLv3
  summary: Test
  description: Test pkg
  source:
    commit:
      full: abcdef0123456789
      date: "20260101"
""")

        url_to_commit_info = {
            "https://example.com/test": (
                "def4567890123456789",  # new full hash
                "def4567",  # new short hash
                "20260102",  # new date
                "0",  # base version
            )
        }
        write_yaml_preserving_comments(yaml_file, {}, url_to_commit_info)

        content = yaml_file.read_text()
        assert "0^20260102gitdef4567" in content
        assert "release: 0" in content


class TestDumpYamlPretty:
    """Test dump_yaml_pretty function behavior."""

    def test_multiline_strings_use_block_scalar(self):
        """Multiline strings should use literal block scalar (|)."""
        data = {"description": "Line 1\nLine 2\nLine 3"}
        output = dump_yaml_pretty(data)
        # ruamel outputs block scalars for multiline strings
        assert "|" in output
        assert "Line 1" in output
        assert "Line 2" in output

    def test_two_space_indentation(self):
        """Output should use 2-space indentation."""
        data = {
            "root": {
                "nested": {
                    "deep": "value"
                }
            }
        }
        output = dump_yaml_pretty(data)
        lines = output.split("\n")
        # Check for consistent 2-space indent
        for line in lines:
            if line and line[0] == " ":
                # Count leading spaces
                spaces = len(line) - len(line.lstrip(" "))
                # Should be multiple of 2
                assert spaces % 2 == 0, f"Non-2-space indent in: {repr(line)}"

    def test_no_key_sorting(self):
        """Keys should maintain insertion order, not be sorted."""
        data = {"zebra": 1, "apple": 2, "mango": 3}
        output = dump_yaml_pretty(data)
        # Find positions of keys in output
        z_pos = output.find("zebra")
        a_pos = output.find("apple")
        m_pos = output.find("mango")
        # Original order: zebra, apple, mango
        assert z_pos < a_pos < m_pos, "Keys should maintain insertion order"

    def test_unicode_preserved(self):
        """Unicode characters should not be escaped."""
        data = {"name": "hyprland", "emoji": "🎨"}
        output = dump_yaml_pretty(data)
        # ruamel preserves unicode by default
        assert "🎨" in output, "Unicode should not be escaped"

    def test_trailing_newline(self):
        """Output should end with newline."""
        data = {"key": "value"}
        output = dump_yaml_pretty(data)
        assert output.endswith("\n")

    def test_no_trailing_spaces(self):
        """No line should have trailing whitespace."""
        data = {"key": "value", "multi": "line1\nline2"}
        output = dump_yaml_pretty(data)
        for line in output.split("\n"):
            if line:  # skip empty lines
                assert line == line.rstrip(), f"Trailing space in: {repr(line)}"

    def test_indent_sequences_false(self):
        """List items should be at parent key indentation (indent_sequences: false)."""
        data = {"items": [{"name": "a"}, {"name": "b"}]}
        output = dump_yaml_pretty(data)
        # List dashes should be at same level as 'items' key
        lines = output.split("\n")
        for i, line in enumerate(lines):
            if "items:" in line:
                # Next line should have dash at parent indent, not deeper
                items_indent = len(lines[i]) - len(lines[i].lstrip(" "))
                if i + 1 < len(lines) and lines[i + 1].strip().startswith("-"):
                    dash_indent = len(lines[i + 1]) - len(lines[i + 1].lstrip(" "))
                    assert dash_indent == items_indent, "Dash should not be indented further"

    def test_single_line_value_inline(self):
        """Single-line values should stay inline, not use block scalar."""
        data = {"name": "test", "version": "1.0"}
        result = dump_yaml_pretty(data)
        assert "name: test" in result
        assert "version: '1.0'" in result or "version: 1.0" in result
