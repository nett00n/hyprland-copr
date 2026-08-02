"""Tests for update-versions script."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Load update-versions.py module (has hyphen, can't import normally)
_spec = importlib.util.spec_from_file_location(
    "update_versions",
    Path(__file__).parent.parent / "scripts" / "update-versions.py",
)
uv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(uv)


class TestCheckoutPin:
    """Tests for checkout_pin (pure function, no mocks needed)."""

    @pytest.mark.parametrize(
        "pkg_data",
        [
            {},
            {"auto_update": {}},
            {"auto_update": {"release_type": ""}},
            {"auto_update": {"release_type": "latest-version"}},
            {"auto_update": {"release_type": "latest-commit"}},
        ],
    )
    def test_no_pin_for_default_and_moving_types(self, pkg_data):
        """Types that move the checkout must not be treated as pins."""
        assert uv.checkout_pin("pkg", pkg_data) is None

    def test_latest_tag_is_not_treated_as_a_pin(self):
        """BUG-0014 guard: mpvpaper's invalid `latest-tag` must keep falling
        through to the default (moving) path, not be treated as a pin. Uses
        exact membership, not startswith("pinned-"), specifically so a typo'd
        release_type degrades the same way here as in the version-resolution
        loop (falls through to default) instead of freezing the checkout.
        """
        pkg_data = {"auto_update": {"release_type": "latest-tag"}}
        assert uv.checkout_pin("mpvpaper", pkg_data) is None

    def test_pinned_tag(self):
        pkg_data = {"auto_update": {"release_type": "pinned-tag", "tag": "1.2.3"}}
        pin = uv.checkout_pin("pkg", pkg_data)
        assert pin == uv.Pin("tag", ("refs/tags/1.2.3",), "pkg")

    def test_pinned_tag_without_tag_is_unresolved(self):
        pkg_data = {"auto_update": {"release_type": "pinned-tag"}}
        pin = uv.checkout_pin("pkg", pkg_data)
        assert pin.kind == "unresolved"
        assert pin.candidates == ()
        assert pin.owner == "pkg"
        assert pin.detail

    def test_pinned_commit(self):
        pkg_data = {
            "auto_update": {"release_type": "pinned-commit"},
            "source": {"commit": {"full": "abc123"}},
        }
        pin = uv.checkout_pin("pkg", pkg_data)
        assert pin == uv.Pin("commit", ("abc123",), "pkg")

    def test_pinned_commit_without_source_commit_is_unresolved(self):
        pkg_data = {"auto_update": {"release_type": "pinned-commit"}}
        pin = uv.checkout_pin("pkg", pkg_data)
        assert pin.kind == "unresolved"
        assert pin.detail

    def test_pinned_commit_with_empty_source_commit_dict_is_unresolved(self):
        pkg_data = {
            "auto_update": {"release_type": "pinned-commit"},
            "source": {"commit": {}},
        }
        pin = uv.checkout_pin("pkg", pkg_data)
        assert pin.kind == "unresolved"

    def test_pinned_version(self):
        pkg_data = {
            "auto_update": {"release_type": "pinned-version"},
            "version": "1.2.3",
        }
        pin = uv.checkout_pin("pkg", pkg_data)
        assert pin == uv.Pin("version", ("refs/tags/v1.2.3", "refs/tags/1.2.3"), "pkg")

    def test_pinned_version_without_version_is_unresolved(self):
        pkg_data = {"auto_update": {"release_type": "pinned-version"}}
        pin = uv.checkout_pin("pkg", pkg_data)
        assert pin.kind == "unresolved"
        assert pin.detail


class TestPullSubmodule:
    """Tests for pull_submodule function."""

    def test_repo_not_exist(self, tmp_path, monkeypatch, capsys):
        """Test warning when repo path doesn't exist."""
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}

        uv.pull_submodule(mod)

        captured = capsys.readouterr()
        assert "does not exist" in captured.err
        assert "skipping pull" in captured.err

    def test_fetch_fails(self, tmp_path, monkeypatch, capsys):
        """Test handling of git fetch failure."""
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = ""

        with patch.object(uv, "run_git", return_value=mock_result):
            uv.pull_submodule(mod)

        captured = capsys.readouterr()
        assert "git fetch failed" in captured.err
        assert "test-pkg" in captured.err

    def test_fetch_fails_with_stderr_msg(self, tmp_path, monkeypatch, capsys):
        """Test fetch failure with stderr message."""
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Connection timeout"

        with patch.object(uv, "run_git", return_value=mock_result):
            uv.pull_submodule(mod)

        captured = capsys.readouterr()
        assert "Connection timeout" in captured.err

    def test_no_branch_symbolic_ref_fails(self, tmp_path, monkeypatch, capsys):
        """Test failure to determine default branch."""
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}

        fetch_result = MagicMock()
        fetch_result.returncode = 0
        head_result = MagicMock()
        head_result.returncode = 1

        with patch.object(uv, "run_git", side_effect=[fetch_result, head_result]):
            uv.pull_submodule(mod)

        captured = capsys.readouterr()
        assert "could not determine default branch" in captured.err

    def test_no_branch_success(self, tmp_path, monkeypatch, capsys):
        """Test successful pull with default branch detection."""
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}

        fetch_result = MagicMock()
        fetch_result.returncode = 0
        head_result = MagicMock()
        head_result.returncode = 0
        head_result.stdout = "refs/remotes/origin/main"
        switch_result = MagicMock()
        switch_result.returncode = 0

        with patch.object(
            uv, "run_git", side_effect=[fetch_result, head_result, switch_result]
        ):
            uv.pull_submodule(mod)

        captured = capsys.readouterr()
        assert "updated test-pkg to main" in captured.err

    def test_branch_specified_success(self, tmp_path, monkeypatch, capsys):
        """Test successful pull with explicit branch."""
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}

        fetch_result = MagicMock()
        fetch_result.returncode = 0
        switch_result = MagicMock()
        switch_result.returncode = 0

        with patch.object(
            uv, "run_git", side_effect=[fetch_result, switch_result]
        ):
            uv.pull_submodule(mod, branch="dev")

        captured = capsys.readouterr()
        assert "updated test-pkg to dev" in captured.err

    def test_checkout_fails(self, tmp_path, monkeypatch, capsys):
        """Test failure during git switch."""
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}

        fetch_result = MagicMock()
        fetch_result.returncode = 0
        head_result = MagicMock()
        head_result.returncode = 0
        head_result.stdout = "refs/remotes/origin/main"
        switch_result = MagicMock()
        switch_result.returncode = 1
        switch_result.stderr = "Branch not found"

        with patch.object(
            uv, "run_git", side_effect=[fetch_result, head_result, switch_result]
        ):
            uv.pull_submodule(mod)

        captured = capsys.readouterr()
        assert "git switch failed" in captured.err
        assert "Branch not found" in captured.err

    def test_fetches_with_tags_flag(self, tmp_path, monkeypatch):
        """--tags: a pinned tag need not be reachable from the tracked branch."""
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}

        fetch_result = MagicMock(returncode=0)
        head_result = MagicMock(returncode=0, stdout="refs/remotes/origin/main")
        switch_result = MagicMock(returncode=0)

        with patch.object(
            uv, "run_git", side_effect=[fetch_result, head_result, switch_result]
        ) as mock_run:
            uv.pull_submodule(mod)

        assert mock_run.call_args_list[0].args[:3] == ("fetch", "--tags", "origin")

    def test_moving_returns_ref_even_when_switch_fails(self, tmp_path, monkeypatch):
        """Version resolution reads the remote-tracking ref, so it must still
        get one back even when the working-tree switch itself failed."""
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}

        fetch_result = MagicMock(returncode=0)
        head_result = MagicMock(returncode=0, stdout="refs/remotes/origin/main")
        switch_result = MagicMock(returncode=1, stderr="boom")

        with patch.object(
            uv, "run_git", side_effect=[fetch_result, head_result, switch_result]
        ):
            ref = uv.pull_submodule(mod)

        assert ref == "origin/main"

    def test_pinned_tag_checks_out_detached(self, tmp_path, monkeypatch, capsys):
        """A pinned-tag package is checked out detached, never via `switch`."""
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}
        pin = uv.Pin("tag", ("refs/tags/v1.2.3",), "pinned-pkg")

        fetch_result = MagicMock(returncode=0)
        head_result = MagicMock(returncode=0, stdout="refs/remotes/origin/main")
        rev_parse_result = MagicMock(returncode=0, stdout="deadbeef" * 5)
        checkout_result = MagicMock(returncode=0)

        with patch.object(
            uv,
            "run_git",
            side_effect=[fetch_result, head_result, rev_parse_result, checkout_result],
        ) as mock_run:
            ref = uv.pull_submodule(mod, pin=pin)

        calls = [c.args for c in mock_run.call_args_list]
        assert ("checkout", "--force", "--detach", "refs/tags/v1.2.3") in calls
        assert not any(c[0] == "switch" for c in calls)
        assert ref == "origin/main"
        captured = capsys.readouterr()
        assert "pinned test-pkg to refs/tags/v1.2.3" in captured.err
        assert "pinned-pkg" in captured.err

    def test_pinned_commit_checks_out_sha(self, tmp_path, monkeypatch):
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}
        pin = uv.Pin("commit", ("abc123def456",), "pinned-pkg")

        fetch_result = MagicMock(returncode=0)
        head_result = MagicMock(returncode=0, stdout="refs/remotes/origin/main")
        rev_parse_result = MagicMock(returncode=0, stdout="abc123def456")
        checkout_result = MagicMock(returncode=0)

        with patch.object(
            uv,
            "run_git",
            side_effect=[fetch_result, head_result, rev_parse_result, checkout_result],
        ) as mock_run:
            uv.pull_submodule(mod, pin=pin)

        calls = [c.args for c in mock_run.call_args_list]
        assert ("checkout", "--force", "--detach", "abc123def456") in calls

    def test_pinned_version_falls_through_to_bare_tag(self, tmp_path, monkeypatch):
        """34/45 packages tag `v<version>`, 6/45 tag bare `<version>` -- the
        v-prefixed candidate is tried first, the bare one second."""
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}
        pin = uv.Pin("version", ("refs/tags/v1.2.3", "refs/tags/1.2.3"), "pinned-pkg")

        fetch_result = MagicMock(returncode=0)
        head_result = MagicMock(returncode=0, stdout="refs/remotes/origin/main")
        v_miss = MagicMock(returncode=1, stdout="")
        bare_hit = MagicMock(returncode=0, stdout="cafebabe" * 5)
        checkout_result = MagicMock(returncode=0)

        with patch.object(
            uv,
            "run_git",
            side_effect=[fetch_result, head_result, v_miss, bare_hit, checkout_result],
        ) as mock_run:
            uv.pull_submodule(mod, pin=pin)

        calls = [c.args for c in mock_run.call_args_list]
        assert ("checkout", "--force", "--detach", "refs/tags/1.2.3") in calls

    def test_pinned_ref_missing_leaves_tree_untouched(
        self, tmp_path, monkeypatch, capsys
    ):
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}
        pin = uv.Pin("tag", ("refs/tags/v99.99.99",), "pinned-pkg")

        fetch_result = MagicMock(returncode=0)
        head_result = MagicMock(returncode=0, stdout="refs/remotes/origin/main")
        rev_parse_miss = MagicMock(returncode=1, stdout="")

        with patch.object(
            uv, "run_git", side_effect=[fetch_result, head_result, rev_parse_miss]
        ) as mock_run:
            ref = uv.pull_submodule(mod, pin=pin)

        assert mock_run.call_count == 3
        assert not any(c.args[0] == "checkout" for c in mock_run.call_args_list)
        assert ref == "origin/main"
        captured = capsys.readouterr()
        assert "none of which exist in the fetched repo" in captured.err
        assert "pinned-pkg" in captured.err

    def test_unresolved_pin_leaves_tree_untouched(self, tmp_path, monkeypatch, capsys):
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}
        pin = uv.Pin(
            "unresolved", (), "pinned-pkg", "pinned-commit with no source.commit.full"
        )

        fetch_result = MagicMock(returncode=0)
        head_result = MagicMock(returncode=0, stdout="refs/remotes/origin/main")

        with patch.object(
            uv, "run_git", side_effect=[fetch_result, head_result]
        ) as mock_run:
            ref = uv.pull_submodule(mod, pin=pin)

        assert mock_run.call_count == 2
        assert ref == "origin/main"
        captured = capsys.readouterr()
        assert "pinned-pkg" in captured.err
        assert "pinned-commit with no source.commit.full" in captured.err

    def test_pinned_checkout_failure_warns(self, tmp_path, monkeypatch, capsys):
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}
        pin = uv.Pin("tag", ("refs/tags/v1.2.3",), "pinned-pkg")

        fetch_result = MagicMock(returncode=0)
        head_result = MagicMock(returncode=0, stdout="refs/remotes/origin/main")
        rev_parse_result = MagicMock(returncode=0, stdout="deadbeef" * 5)
        checkout_result = MagicMock(returncode=1, stderr="fatal: bad object")

        with patch.object(
            uv,
            "run_git",
            side_effect=[fetch_result, head_result, rev_parse_result, checkout_result],
        ):
            uv.pull_submodule(mod, pin=pin)

        captured = capsys.readouterr()
        assert "git checkout failed" in captured.err
        assert "fatal: bad object" in captured.err

    def test_pinned_with_explicit_branch_skips_symbolic_ref(
        self, tmp_path, monkeypatch
    ):
        repo_dir = tmp_path / "submodules" / "test"
        repo_dir.mkdir(parents=True)
        monkeypatch.setattr(uv, "ROOT", tmp_path)
        mod = {"name": "test-pkg", "path": "submodules/test"}
        pin = uv.Pin("tag", ("refs/tags/v1.2.3",), "pinned-pkg")

        fetch_result = MagicMock(returncode=0)
        rev_parse_result = MagicMock(returncode=0, stdout="deadbeef" * 5)
        checkout_result = MagicMock(returncode=0)

        with patch.object(
            uv,
            "run_git",
            side_effect=[fetch_result, rev_parse_result, checkout_result],
        ) as mock_run:
            ref = uv.pull_submodule(mod, branch="dev", pin=pin)

        assert mock_run.call_count == 3
        assert ref == "origin/dev"


class TestMain:
    """Tests for main function."""

    def test_no_gitmodules(self, tmp_path, monkeypatch):
        """Test exit when .gitmodules not found."""
        monkeypatch.setattr(uv, "GITMODULES", tmp_path / ".gitmodules")

        with pytest.raises(SystemExit) as exc_info:
            uv.main()
        assert exc_info.value.code == 1

    def test_pinned_version_skipped(self, tmp_path, monkeypatch, capsys):
        """Test that pinned-version release type is skipped."""
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test.git\n"
        )
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)

        packages = {
            "test": {
                "url": "https://github.com/test/test.git",
                "auto_update": {"release_type": "pinned-version"},
            }
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(uv, "pull_submodule"):
                    with patch.object(uv, "fetch_tags") as mock_fetch:
                        with patch.object(
                            uv, "write_yaml_preserving_comments", return_value={}
                        ):
                            mock_parse.return_value = [
                                {
                                    "name": "test",
                                    "path": "submodules/test",
                                    "url": "https://github.com/test/test.git",
                                }
                            ]
                            uv.main()

        mock_fetch.assert_not_called()

    def test_pinned_commit_skipped(self, tmp_path, monkeypatch, capsys):
        """Test that pinned-commit release type is skipped."""
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test.git\n"
        )
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)

        packages = {
            "test": {
                "url": "https://github.com/test/test.git",
                "auto_update": {"release_type": "pinned-commit"},
            }
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(uv, "pull_submodule"):
                    with patch.object(
                        uv, "get_submodule_commit_with_base"
                    ) as mock_commit:
                        with patch.object(
                            uv, "write_yaml_preserving_comments", return_value={}
                        ):
                            mock_parse.return_value = [
                                {
                                    "name": "test",
                                    "path": "submodules/test",
                                    "url": "https://github.com/test/test.git",
                                }
                            ]
                            uv.main()

        mock_commit.assert_not_called()

    def test_pinned_tag(self, tmp_path, monkeypatch, capsys):
        """Test pinned-tag release type fetches specific tag."""
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test.git\n"
        )
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)

        packages = {
            "test": {
                "url": "https://github.com/test/test.git",
                "auto_update": {"release_type": "pinned-tag", "tag": "v1.2.3"},
            }
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(uv, "pull_submodule"):
                    with patch.object(
                        uv, "get_tag_commit"
                    ) as mock_tag_commit:
                        with patch.object(
                            uv, "write_yaml_preserving_comments", return_value={}
                        ):
                            mock_parse.return_value = [
                                {
                                    "name": "test",
                                    "path": "submodules/test",
                                    "url": "https://github.com/test/test.git",
                                }
                            ]
                            mock_tag_commit.return_value = (
                                "abcdef123456",
                                "abcdef1",
                                "20260327",
                                "1.2.3",
                            )
                            uv.main()

        mock_tag_commit.assert_called()
        captured = capsys.readouterr()
        assert "1.2.3^20260327gitabcdef1" in captured.out

    def test_latest_version(self, tmp_path, monkeypatch, capsys):
        """Test latest-version release type uses semver only."""
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test.git\n"
        )
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)

        packages = {
            "test": {
                "url": "https://github.com/test/test.git",
                "auto_update": {"release_type": "latest-version"},
            }
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(uv, "pull_submodule"):
                    with patch.object(uv, "fetch_tags") as mock_fetch:
                        with patch.object(uv, "latest_semver") as mock_semver:
                            with patch.object(
                                uv, "write_yaml_preserving_comments", return_value={}
                            ):
                                mock_parse.return_value = [
                                    {
                                        "name": "test",
                                        "path": "submodules/test",
                                        "url": "https://github.com/test/test.git",
                                    }
                                ]
                                mock_fetch.return_value = ["v1.2.3", "v1.0.0"]
                                mock_semver.return_value = "v1.2.3"
                                uv.main()

        captured = capsys.readouterr()
        assert "latest: 1.2.3" in captured.out

    def test_latest_commit(self, tmp_path, monkeypatch, capsys):
        """Test latest-commit release type fetches HEAD commit."""
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test.git\n"
        )
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)

        packages = {
            "test": {
                "url": "https://github.com/test/test.git",
                "auto_update": {"release_type": "latest-commit"},
            }
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(uv, "pull_submodule"):
                    with patch.object(
                        uv, "get_submodule_commit_with_base"
                    ) as mock_commit:
                        with patch.object(
                            uv, "write_yaml_preserving_comments", return_value={}
                        ):
                            mock_parse.return_value = [
                                {
                                    "name": "test",
                                    "path": "submodules/test",
                                    "url": "https://github.com/test/test.git",
                                }
                            ]
                            mock_commit.return_value = (
                                "abcdef123456",
                                "abcdef1",
                                "20260327",
                                "1.0.0",
                            )
                            uv.main()

        captured = capsys.readouterr()
        assert "1.0.0^20260327gitabcdef1" in captured.out

    def test_default_semver(self, tmp_path, monkeypatch, capsys):
        """Test default (no release_type) uses semver when available."""
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test.git\n"
        )
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)

        packages = {
            "test": {
                "url": "https://github.com/test/test.git",
                "auto_update": {},
            }
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(uv, "pull_submodule"):
                    with patch.object(uv, "fetch_tags") as mock_fetch:
                        with patch.object(uv, "latest_semver") as mock_semver:
                            with patch.object(
                                uv, "write_yaml_preserving_comments", return_value={}
                            ):
                                mock_parse.return_value = [
                                    {
                                        "name": "test",
                                        "path": "submodules/test",
                                        "url": "https://github.com/test/test.git",
                                    }
                                ]
                                mock_fetch.return_value = ["v2.0.0"]
                                mock_semver.return_value = "v2.0.0"
                                uv.main()

        captured = capsys.readouterr()
        assert "latest: 2.0.0" in captured.out

    def test_default_commit_fallback(self, tmp_path, monkeypatch, capsys):
        """Test default falls back to commit when no semver found."""
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test.git\n"
        )
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)

        packages = {
            "test": {
                "url": "https://github.com/test/test.git",
                "auto_update": {},
            }
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(uv, "pull_submodule"):
                    with patch.object(uv, "fetch_tags") as mock_fetch:
                        with patch.object(uv, "latest_semver") as mock_semver:
                            with patch.object(
                                uv, "get_submodule_commit_with_base"
                            ) as mock_commit:
                                with patch.object(
                                    uv,
                                    "write_yaml_preserving_comments",
                                    return_value={},
                                ):
                                    mock_parse.return_value = [
                                        {
                                            "name": "test",
                                            "path": "submodules/test",
                                            "url": "https://github.com/test/test.git",
                                        }
                                    ]
                                    mock_fetch.return_value = []
                                    mock_semver.return_value = None
                                    mock_commit.return_value = (
                                        "abcdef123456",
                                        "abcdef1",
                                        "20260327",
                                        "0",
                                    )
                                    uv.main()

        captured = capsys.readouterr()
        assert "0^20260327gitabcdef1" in captured.out

    def test_no_packages_yaml(self, tmp_path, monkeypatch, capsys):
        """Test warning when packages.yaml not found."""
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test.git\n"
        )
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        monkeypatch.setattr(uv, "PACKAGES_YAML", tmp_path / "packages.yaml")

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", side_effect=SystemExit()):
                with patch.object(uv, "pull_submodule"):
                    with patch.object(uv, "fetch_tags") as mock_fetch:
                        with patch.object(uv, "latest_semver") as mock_semver:
                            mock_parse.return_value = [
                                {
                                    "name": "test",
                                    "path": "submodules/test",
                                    "url": "https://github.com/test/test.git",
                                }
                            ]
                            mock_fetch.return_value = ["v1.0.0"]
                            mock_semver.return_value = "v1.0.0"
                            uv.main()

        captured = capsys.readouterr()
        assert "packages.yaml not found" in captured.err

    def test_packages_yaml_updated(self, tmp_path, monkeypatch, capsys):
        """Test that write_yaml_preserving_comments is called with correct args."""
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test.git\n"
        )
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)

        packages = {
            "test": {
                "url": "https://github.com/test/test.git",
                "auto_update": {"release_type": "latest-version"},
            }
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(uv, "pull_submodule"):
                    with patch.object(uv, "fetch_tags") as mock_fetch:
                        with patch.object(uv, "latest_semver") as mock_semver:
                            with patch.object(
                                uv, "write_yaml_preserving_comments"
                            ) as mock_write:
                                mock_parse.return_value = [
                                    {
                                        "name": "test",
                                        "path": "submodules/test",
                                        "url": "https://github.com/test/test.git",
                                    }
                                ]
                                mock_fetch.return_value = ["v1.5.0"]
                                mock_semver.return_value = "v1.5.0"
                                mock_write.return_value = {
                                    "test": ("1.0.0", "1.5.0")
                                }
                                uv.main()

        mock_write.assert_called_once()
        captured = capsys.readouterr()
        assert "updated packages.yaml:" in captured.err
        assert "test: 1.0.0 -> 1.5.0" in captured.err

    def test_shared_url_packages_resolved_independently(
        self, tmp_path, monkeypatch, capsys
    ):
        """Regression: two packages sharing one submodule url (e.g. a stable
        package and its "-git" sibling) must each get their own release_type
        applied. Keying by url instead of package name let the "-git" sibling's
        config silently shadow the stable package's, freezing it forever
        (see docs/bugs.md / issue #8).
        """
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test\n"
        )
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)

        # "Stable" has no auto_update (default: semver). "Stable-git" tracks
        # latest-commit. Both point at the exact same url.
        packages = {
            "Stable": {
                "url": "https://github.com/test/test",
            },
            "Stable-git": {
                "url": "https://github.com/test/test",
                "auto_update": {"release_type": "latest-commit"},
            },
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(uv, "pull_submodule"):
                    with patch.object(uv, "fetch_tags") as mock_fetch:
                        with patch.object(uv, "latest_semver") as mock_semver:
                            with patch.object(
                                uv, "get_submodule_commit_with_base"
                            ) as mock_commit:
                                with patch.object(
                                    uv, "write_yaml_preserving_comments"
                                ) as mock_write:
                                    mock_parse.return_value = [
                                        {
                                            "name": "test",
                                            "path": "submodules/test",
                                            "url": "https://github.com/test/test",
                                        }
                                    ]
                                    mock_fetch.return_value = ["v0.56.1"]
                                    mock_semver.return_value = "v0.56.1"
                                    mock_commit.return_value = (
                                        "924a3573abcdef",
                                        "924a357",
                                        "20260728",
                                        "0.56.0",
                                    )
                                    mock_write.return_value = {}
                                    uv.main()

        mock_write.assert_called_once()
        _, args, _ = mock_write.mock_calls[0]
        pkg_to_latest, pkg_to_commit_info = args[1], args[2]

        # Stable must get its semver bump ...
        assert pkg_to_latest == {"Stable": "0.56.1"}
        # ... and Stable-git must independently get its commit-based version,
        # not be skipped because "Stable" already claimed this url.
        assert pkg_to_commit_info == {
            "Stable-git": ("924a3573abcdef", "924a357", "20260728", "0.56.0")
        }

        captured = capsys.readouterr()
        assert "latest: 0.56.1" in captured.out
        assert "0.56.0^20260728git924a357" in captured.out

    def test_pin_wins_over_moving_sibling_on_shared_url(
        self, tmp_path, monkeypatch, capsys
    ):
        """Regression for the fix's core claim: a pinned package must win the
        submodule checkout over a moving sibling sharing the same url, and the
        sibling must still get its own version resolved -- against the remote
        branch, not the (now pinned) working tree.
        """
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test\n"
        )
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)
        monkeypatch.setattr(uv, "ROOT", tmp_path)

        packages = {
            "Pinned": {
                "url": "https://github.com/test/test",
                "auto_update": {"release_type": "pinned-tag", "tag": "v1.0.0"},
            },
            "Sibling-git": {
                "url": "https://github.com/test/test",
                "auto_update": {"release_type": "latest-commit"},
            },
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(
                    uv, "pull_submodule", return_value="origin/main"
                ) as mock_pull:
                    with patch.object(uv, "get_tag_commit") as mock_tag_commit:
                        with patch.object(
                            uv, "get_submodule_commit_with_base"
                        ) as mock_commit:
                            with patch.object(
                                uv, "write_yaml_preserving_comments", return_value={}
                            ):
                                mock_parse.return_value = [
                                    {
                                        "name": "test",
                                        "path": "submodules/test",
                                        "url": "https://github.com/test/test",
                                    }
                                ]
                                mock_tag_commit.return_value = (
                                    "aaa111",
                                    "aaa111",
                                    "20260101",
                                    "1.0.0",
                                )
                                mock_commit.return_value = (
                                    "bbb222",
                                    "bbb222",
                                    "20260728",
                                    "0.56.0",
                                )
                                uv.main()

        # pull_submodule ran once (one physical checkout) and got the pin
        # from "Pinned", not from "Sibling-git".
        mock_pull.assert_called_once()
        assert mock_pull.call_args.kwargs["pin"].owner == "Pinned"

        # Sibling-git resolved its version against the remote-tracking ref
        # returned by pull_submodule, not the working tree.
        repo = tmp_path / "submodules" / "test"
        mock_commit.assert_called_once_with(repo, "origin/main")

        captured = capsys.readouterr()
        assert "note:" in captured.err
        assert "Pinned" in captured.err
        assert "Sibling-git" in captured.err

    def test_conflicting_pins_first_in_file_wins(self, tmp_path, monkeypatch, capsys):
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test\n"
        )
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)

        packages = {
            "First": {
                "url": "https://github.com/test/test",
                "auto_update": {"release_type": "pinned-tag", "tag": "v1.0.0"},
            },
            "Second": {
                "url": "https://github.com/test/test",
                "auto_update": {"release_type": "pinned-tag", "tag": "v2.0.0"},
            },
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(
                    uv, "pull_submodule", return_value="origin/main"
                ) as mock_pull:
                    with patch.object(uv, "get_tag_commit", return_value=None):
                        with patch.object(
                            uv, "write_yaml_preserving_comments", return_value={}
                        ):
                            mock_parse.return_value = [
                                {
                                    "name": "test",
                                    "path": "submodules/test",
                                    "url": "https://github.com/test/test",
                                }
                            ]
                            uv.main()

        assert mock_pull.call_args.kwargs["pin"].owner == "First"
        captured = capsys.readouterr()
        assert "warning:" in captured.err
        assert "First" in captured.err
        assert "Second" in captured.err

    def test_identical_pins_do_not_warn(self, tmp_path, monkeypatch, capsys):
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test\n"
        )
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)

        packages = {
            "First": {
                "url": "https://github.com/test/test",
                "auto_update": {"release_type": "pinned-tag", "tag": "v1.0.0"},
            },
            "Second": {
                "url": "https://github.com/test/test",
                "auto_update": {"release_type": "pinned-tag", "tag": "v1.0.0"},
            },
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(uv, "pull_submodule", return_value="origin/main"):
                    with patch.object(uv, "get_tag_commit", return_value=None):
                        with patch.object(
                            uv, "write_yaml_preserving_comments", return_value={}
                        ):
                            mock_parse.return_value = [
                                {
                                    "name": "test",
                                    "path": "submodules/test",
                                    "url": "https://github.com/test/test",
                                }
                            ]
                            uv.main()

        captured = capsys.readouterr()
        assert "warning:" not in captured.err

    def test_latest_commit_resolves_remote_ref_not_head(
        self, tmp_path, monkeypatch, capsys
    ):
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test.git\n"
        )
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)
        monkeypatch.setattr(uv, "ROOT", tmp_path)

        packages = {
            "test": {
                "url": "https://github.com/test/test.git",
                "auto_update": {"release_type": "latest-commit"},
            }
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(uv, "pull_submodule", return_value="origin/main"):
                    with patch.object(
                        uv, "get_submodule_commit_with_base"
                    ) as mock_commit:
                        with patch.object(
                            uv, "write_yaml_preserving_comments", return_value={}
                        ):
                            mock_parse.return_value = [
                                {
                                    "name": "test",
                                    "path": "submodules/test",
                                    "url": "https://github.com/test/test.git",
                                }
                            ]
                            mock_commit.return_value = (
                                "abcdef123456",
                                "abcdef1",
                                "20260327",
                                "1.0.0",
                            )
                            uv.main()

        repo = tmp_path / "submodules" / "test"
        mock_commit.assert_called_once_with(repo, "origin/main")

    def test_default_fallback_resolves_remote_ref(self, tmp_path, monkeypatch):
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test.git\n"
        )
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)
        monkeypatch.setattr(uv, "ROOT", tmp_path)

        packages = {
            "test": {
                "url": "https://github.com/test/test.git",
                "auto_update": {},
            }
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(uv, "pull_submodule", return_value="origin/main"):
                    with patch.object(uv, "fetch_tags", return_value=[]):
                        with patch.object(uv, "latest_semver", return_value=None):
                            with patch.object(
                                uv, "get_submodule_commit_with_base"
                            ) as mock_commit:
                                with patch.object(
                                    uv,
                                    "write_yaml_preserving_comments",
                                    return_value={},
                                ):
                                    mock_parse.return_value = [
                                        {
                                            "name": "test",
                                            "path": "submodules/test",
                                            "url": "https://github.com/test/test.git",
                                        }
                                    ]
                                    mock_commit.return_value = (
                                        "aaa",
                                        "aaa",
                                        "20260101",
                                        None,
                                    )
                                    uv.main()

        repo = tmp_path / "submodules" / "test"
        mock_commit.assert_called_once_with(repo, "origin/main")

    def test_skips_commit_resolution_when_pull_failed(
        self, tmp_path, monkeypatch, capsys
    ):
        gitmodules = tmp_path / ".gitmodules"
        gitmodules.write_text(
            '[submodule "test"]\n'
            "\tpath = submodules/test\n"
            "\turl = https://github.com/test/test.git\n"
        )
        monkeypatch.setattr(uv, "GITMODULES", gitmodules)
        packages_yaml = tmp_path / "packages.yaml"
        packages_yaml.write_text("")
        monkeypatch.setattr(uv, "PACKAGES_YAML", packages_yaml)

        packages = {
            "test": {
                "url": "https://github.com/test/test.git",
                "auto_update": {"release_type": "latest-commit"},
            }
        }

        with patch.object(uv, "parse_gitmodules") as mock_parse:
            with patch.object(uv, "get_packages", return_value=packages):
                with patch.object(uv, "pull_submodule", return_value=None):
                    with patch.object(
                        uv, "get_submodule_commit_with_base"
                    ) as mock_commit:
                        with patch.object(
                            uv, "write_yaml_preserving_comments", return_value={}
                        ):
                            mock_parse.return_value = [
                                {
                                    "name": "test",
                                    "path": "submodules/test",
                                    "url": "https://github.com/test/test.git",
                                }
                            ]
                            uv.main()

        mock_commit.assert_not_called()
        captured = capsys.readouterr()
        assert "submodule not pulled" in captured.err
        assert "latest: null" in captured.out
