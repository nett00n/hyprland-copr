"""Tests for lib.upstream (#COPR-0004)."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lib import paths
from tests.git_helpers import git as _git
from lib.upstream import (
    UpstreamError,
    checkout_worktree,
    ensure_mirror,
    fetch_mirror,
    find_upstream,
    list_upstreams,
    mirror_path,
    sync_upstream,
    upstream_name,
    worktree_path,
    TagFetch,
    fetch_tags,
    get_changelog_info,
    get_commit_info,
    get_commit,
    get_commit_with_base,
    get_tag_commit,
    get_tag_info,
    resolve_module,
)


def _cp(returncode=0, stdout="", stderr=""):
    """Build a CompletedProcess the way run_git() would return it."""
    return subprocess.CompletedProcess(["git"], returncode, stdout, stderr)


class TestFetchTags:
    """Tests for fetch_tags function."""

    @patch("lib.upstream.run_git")
    def test_fetch_tags_success(self, mock_run):
        """Test successful tag fetch."""
        mock_run.return_value = _cp(
            returncode=0,
            stdout=(
                "abc123\trefs/tags/v1.0.0\n"
                "def456\trefs/tags/v2.0.0\n"
                "ghi789\trefs/tags/v2.0.0^{}\n"
            ),
        )

        result = fetch_tags("https://github.com/hyprwm/hyprland.git")

        assert result.error is None
        assert "v1.0.0" in result.tags
        assert "v2.0.0" in result.tags
        # Dereferenced tag (^{}) should not be in results
        assert not any("^{}" in tag for tag in result.tags)

    @patch("lib.upstream.run_git")
    def test_fetch_tags_command_failure(self, mock_run, capsys):
        """Test handling of git command failure."""
        mock_run.return_value = _cp(returncode=128, stdout="")

        result = fetch_tags("https://invalid.git")

        assert result.tags == []
        assert result.error is not None
        captured = capsys.readouterr()
        assert "warning" in captured.err

    @patch("lib.upstream.run_git")
    def test_fetch_tags_timeout(self, mock_run, capsys):
        """Test handling of timeout (run_git reports it as returncode=124)."""
        mock_run.return_value = _cp(
            returncode=124,
            stdout="",
            stderr="command timed out after 30s: git ls-remote",
        )

        result = fetch_tags("https://slow-repo.git")

        assert result.tags == []
        assert result.error is not None
        assert "timeout" in result.error
        captured = capsys.readouterr()
        assert "warning" in captured.err
        assert "timeout" in captured.err

    @patch("lib.upstream.run_git")
    def test_fetch_tags_failure_vs_no_tags_are_distinguishable(self, mock_run):
        """A fetch failure and a genuinely tagless upstream must not collapse
        to the same (tags=[], error=None) shape -- that collapse is BUG-0100's
        root cause for the update-versions.py aggregate report."""
        mock_run.return_value = _cp(returncode=0, stdout="")
        no_tags = fetch_tags("https://example.com/no-tags.git")
        assert no_tags == TagFetch([], None)

        mock_run.return_value = _cp(returncode=1, stdout="")
        failed = fetch_tags("https://example.com/broken.git")
        assert failed.tags == []
        assert failed.error is not None
        assert failed != no_tags

    @patch("lib.upstream.run_git")
    def test_fetch_tags_malformed_output(self, mock_run):
        """Test handling of malformed output."""
        mock_run.return_value = _cp(
            returncode=0,
            stdout=("malformed line\nabc123\trefs/tags/v1.0.0\nanother bad line\n"),
        )

        result = fetch_tags("https://example.com/repo.git")

        # Should only have the properly formatted line
        assert "v1.0.0" in result.tags
        assert result.error is None


class TestResolveModule:
    """Tests for resolve_module function."""

    def test_resolve_module_found(self):
        """Test finding a module by name."""
        modules = [
            {"name": "hyprland", "path": "submodules/hyprwm/hyprland", "url": "..."},
            {
                "name": "hyprpicker",
                "path": "submodules/hyprwm/hyprpicker",
                "url": "...",
            },
        ]
        result = resolve_module(modules, "hyprland")
        assert result is not None
        assert result["name"] == "hyprland"

    def test_resolve_module_case_insensitive(self):
        """Test that resolution is case-insensitive."""
        modules = [
            {"name": "Hyprland", "path": "submodules/hyprwm/Hyprland", "url": "..."},
        ]
        result = resolve_module(modules, "hyprland")
        assert result is not None

    def test_resolve_module_not_found(self):
        """Test when module is not found."""
        modules = [
            {"name": "pkg1", "path": "submodules/org/pkg1", "url": "..."},
        ]
        result = resolve_module(modules, "nonexistent")
        assert result is None

    def test_resolve_module_empty_list(self):
        """Test with empty module list."""
        result = resolve_module([], "anything")
        assert result is None


@patch("lib.upstream.run_git")
def test_get_tag_info_not_found(mock_run):
    """Test get_tag_info when tag doesn't exist."""
    mock_run.return_value = _cp(returncode=0, stdout="")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_info(Path(tmpdir), "1.0.0")
        assert result is None


@patch("lib.upstream.run_git")
def test_get_tag_info_with_lightweight_tag(mock_run):
    """Test get_tag_info with lightweight tag (no annotated info)."""
    # First call: git tag -l (tag exists)
    check1 = _cp(returncode=0, stdout="v1.0.0\n")
    # Second call: git cat-file tag (lightweight tag, fails)
    cat = _cp(returncode=1, stdout="")
    # Third call: git log (fallback for date/body)
    log = _cp(returncode=0, stdout="2024-01-01T00:00:00+00:00\nRelease v1.0.0\n")
    # Fourth call: git rev-list for commit hash
    rev = _cp(returncode=0, stdout="abc123def456\n")

    mock_run.side_effect = [check1, cat, log, rev]

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_info(Path(tmpdir), "1.0.0")
        assert result is not None
        assert result["tag"] == "v1.0.0"
        assert "2024-01-01" in result["published_at"]
        assert result["body"] == "Release v1.0.0"
        assert result["commit"] == "abc123def456"


@patch("lib.upstream.run_git")
def test_get_commit_info_success(mock_run):
    """Test get_commit_info with valid commit."""
    mock_run.return_value = _cp(
        returncode=0,
        stdout="abc123def456\n2024-01-01T00:00:00+00:00\nCommit message\nwith body\n",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit_info(Path(tmpdir), "HEAD")
        assert result is not None
        assert result["commit"] == "abc123def456"
        assert "2024-01-01" in result["published_at"]
        assert "Commit message" in result["body"]


@patch("lib.upstream.run_git")
def test_get_commit_info_failure(mock_run):
    """Test get_commit_info when git command fails."""
    mock_run.return_value = _cp(returncode=128, stdout="")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit_info(Path(tmpdir), "invalid")
        assert result is None


@patch("lib.upstream.get_commit_info")
@patch("lib.upstream.get_tag_info")
def test_get_changelog_info_tag_preferred(mock_tag_info, mock_commit_info):
    """Test that get_changelog_info prefers tag over commit."""
    mock_tag_info.return_value = {
        "published_at": "2024-01-01T00:00:00+00:00",
        "body": "Tag release",
        "tag": "v1.0.0",
        "commit": "abc123",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_changelog_info(Path(tmpdir), "1.0.0", "def456")
        assert result["tag"] == "v1.0.0"
        # commit_info should not be called since tag exists
        mock_commit_info.assert_not_called()


@patch("lib.upstream.get_commit_info")
@patch("lib.upstream.get_tag_info")
def test_get_changelog_info_fallback_to_commit(mock_tag_info, mock_commit_info):
    """Test that get_changelog_info falls back to commit."""
    mock_tag_info.return_value = None
    mock_commit_info.return_value = {
        "published_at": "2024-01-01T00:00:00+00:00",
        "body": "Commit message",
        "commit": "def456",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_changelog_info(Path(tmpdir), "1.0.0", "def456")
        assert result["commit"] == "def456"
        assert "Commit message" in result["body"]


@patch("lib.upstream.run_git")
def test_get_commit_success(mock_run):
    """Test get_commit with valid commit."""
    mock_run.return_value = _cp(returncode=0, stdout="abc123def456 20240101\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit(Path(tmpdir))
        assert result is not None
        assert result[0] == "abc123def456"  # full hash
        assert result[1] == "abc123d"  # short hash
        assert result[2] == "20240101"  # date


@patch("lib.upstream.run_git")
def test_get_commit_failure(mock_run):
    """Test get_commit with command failure (e.g. a timeout)."""
    mock_run.return_value = _cp(returncode=124, stderr="command timed out after 300s")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit(Path(tmpdir))
        assert result is None


@patch("lib.upstream.get_commit")
@patch("lib.upstream.run_git")
def test_get_commit_with_base_success(mock_run, mock_get_commit):
    """Test get_commit_with_base finds base semver."""
    mock_get_commit.return_value = ("abc123def456", "abc123d", "20240101")
    mock_run.return_value = _cp(returncode=0, stdout="v1.5.0\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit_with_base(Path(tmpdir))
        assert result is not None
        assert result[0] == "abc123def456"
        assert result[3] == "1.5.0"  # v-prefix stripped


@patch("lib.upstream.run_git")
def test_get_commit_accepts_ref(mock_run):
    """A ref other than HEAD (e.g. origin/<branch>) must reach `git log`, so
    version resolution doesn't depend on the working tree's checked-out
    commit (see docs/BUGS.md BUG-0033)."""
    mock_run.return_value = _cp(returncode=0, stdout="abc123def456 20240101\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        get_commit(Path(tmpdir), ref="origin/main")

    argv = mock_run.call_args[0]
    assert argv[-1] == "origin/main"


@patch("lib.upstream.run_git")
def test_get_commit_defaults_to_head(mock_run):
    mock_run.return_value = _cp(returncode=0, stdout="abc123def456 20240101\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        get_commit(Path(tmpdir))

    argv = mock_run.call_args[0]
    assert argv[-1] == "HEAD"


@patch("lib.upstream.get_commit")
@patch("lib.upstream.run_git")
def test_get_commit_with_base_threads_ref(mock_run, mock_get_commit):
    """get_commit_with_base must pass `ref` through to
    get_commit, and describe the nearest semver tag from the
    *resolved commit hash* rather than the literal ref -- so it can't
    disagree with get_commit if a remote-tracking ref moves
    between the two subprocess calls."""
    mock_get_commit.return_value = ("abc123def456", "abc123d", "20240101")
    mock_run.return_value = _cp(returncode=0, stdout="v1.5.0\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit_with_base(Path(tmpdir), ref="origin/main")

    mock_get_commit.assert_called_once_with(Path(tmpdir), "origin/main")
    describe_argv = mock_run.call_args[0]
    assert describe_argv[-1] == "abc123def456"
    assert result[3] == "1.5.0"


@patch("lib.upstream.run_git")
def test_get_tag_commit_success(mock_run):
    """Test get_tag_commit with valid tag."""
    rev = _cp(returncode=0, stdout="abc123def456\n")
    date_result = _cp(returncode=0, stdout="20240101\n")
    describe = _cp(returncode=0, stdout="v1.5.0\n")

    mock_run.side_effect = [rev, date_result, describe]

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_commit(Path(tmpdir), "v2.0.0")
        assert result is not None
        assert result[0] == "abc123def456"
        assert result[1] == "abc123d"
        assert result[2] == "20240101"
        assert result[3] == "1.5.0"


@patch("lib.upstream.run_git")
def test_get_tag_commit_invalid_tag(mock_run):
    """Test get_tag_commit with invalid tag."""
    mock_run.return_value = _cp(returncode=128, stdout="")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_commit(Path(tmpdir), "invalid")
        assert result is None


@patch("lib.upstream.run_git")
def test_get_tag_info_with_tagger_timestamp(mock_run):
    """Test extracting timestamp from tagger line."""
    check = _cp(returncode=0, stdout="v1.0.0\n")
    cat = _cp(
        returncode=0,
        stdout=(
            "object abc123\n"
            "type commit\n"
            "tag v1.0.0\n"
            "tagger John Doe <john@example.com> 1704067200 +0000\n"
            "\n"
            "Release\n"
        ),
    )
    log = _cp(returncode=1, stdout="")
    rev = _cp(returncode=0, stdout="abc123def456\n")

    mock_run.side_effect = [check, cat, log, rev]

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_info(Path(tmpdir), "1.0.0")
        assert result is not None
        # Verify timestamp was parsed
        assert "2024-01-01" in result["published_at"]


@patch("lib.upstream.run_git")
def test_get_tag_info_no_tagger_uses_log(mock_run):
    """Test fallback to log when tagger line missing."""
    check = _cp(returncode=0, stdout="v1.0.0\n")
    cat = _cp(returncode=0, stdout="object abc123\ntype commit\n\n")
    log = _cp(returncode=0, stdout="2024-01-01T10:00:00+00:00\nRelease message\n")
    rev = _cp(returncode=0, stdout="abc123def456\n")

    mock_run.side_effect = [check, cat, log, rev]

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_info(Path(tmpdir), "1.0.0")
        assert result is not None
        assert "2024-01-01" in result["published_at"]


@patch("lib.upstream.run_git")
def test_get_commit_info_invalid_date(mock_run):
    """Test get_commit_info with invalid ISO date."""
    mock_run.return_value = _cp(returncode=0, stdout="abc123\ninvalid-date\nbody\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit_info(Path(tmpdir), "HEAD")
        assert result is None


@patch("lib.upstream.run_git")
def test_get_commit_info_missing_fields(mock_run):
    """Test get_commit_info with missing fields."""
    mock_run.return_value = _cp(
        returncode=0, stdout="abc123\n"
    )  # missing date and body

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit_info(Path(tmpdir), "HEAD")
        assert result is None


@patch("lib.upstream.get_commit_info")
@patch("lib.upstream.get_tag_info")
def test_get_changelog_info_no_tag_no_commit(mock_tag_info, mock_commit_info):
    """Test get_changelog_info when both tag and commit fail."""
    mock_tag_info.return_value = None
    mock_commit_info.return_value = None

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_changelog_info(Path(tmpdir), "1.0.0", "abc123")
        assert result is None


@patch("lib.upstream.run_git")
def test_get_commit_with_multiple_fields(mock_run):
    """Test get_commit with output containing multiple fields."""
    mock_run.return_value = _cp(
        returncode=0, stdout="abc123def456 20240101 extra stuff\n"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit(Path(tmpdir))
        assert result is not None
        # Should use first two parts
        assert result[0] == "abc123def456"
        assert result[2] == "20240101"


@patch("lib.upstream.run_git")
def test_get_commit_empty_output(mock_run):
    """Test get_commit with empty output."""
    mock_run.return_value = _cp(returncode=0, stdout="")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit(Path(tmpdir))
        assert result is None


@patch("lib.upstream.run_git")
def test_get_commit_with_base_no_commit(mock_run):
    """Test get_commit_with_base when commit call fails."""
    mock_run.return_value = _cp(returncode=128, stdout="")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit_with_base(Path(tmpdir))
        assert result is None


@patch("lib.upstream.get_commit")
@patch("lib.upstream.run_git")
def test_get_commit_with_base_no_semver(mock_run, mock_get_commit):
    """Test get_commit_with_base when no semver tag found."""
    mock_get_commit.return_value = ("abc123def456", "abc123d", "20240101")
    mock_run.return_value = _cp(returncode=128, stdout="")  # tag not found

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_commit_with_base(Path(tmpdir))
        assert result is not None
        assert result[3] is None  # base_semver should be None


@patch("lib.upstream.run_git")
def test_get_tag_commit_date_failure(mock_run):
    """Test get_tag_commit when date retrieval fails."""
    rev = _cp(returncode=0, stdout="abc123def456\n")
    date_result = _cp(returncode=1, stdout="")

    mock_run.side_effect = [rev, date_result]

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_commit(Path(tmpdir), "v1.0.0")
        assert result is None


@patch("lib.upstream.run_git")
def test_get_tag_commit_with_timeout(mock_run):
    """A run_git timeout (returncode=124) on the first call must not raise."""
    mock_run.return_value = _cp(returncode=124, stderr="command timed out after 10s")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_tag_commit(Path(tmpdir), "v1.0.0")
        assert result is None


class TestUpstreamPaths:
    """#COPR-0004: url -> mirror/worktree layout."""

    def test_upstream_name_strips_dot_git_and_keeps_org_name(self):
        assert (
            upstream_name("https://github.com/hyprwm/hyprland.git") == "hyprwm/hyprland"
        )
        assert upstream_name("https://github.com/hyprwm/hyprland/") == "hyprwm/hyprland"

    def test_upstream_name_takes_last_two_segments(self):
        assert upstream_name("https://gitlab.com/a/b/c/repo") == "c/repo"

    def test_upstream_name_single_segment_falls_back_to_host(self):
        assert upstream_name("https://example.com/repo") == "example.com/repo"

    def test_mirror_and_worktree_paths(self, upstream_repo):
        url = "https://github.com/acme/widget.git"
        assert mirror_path(url) == paths.UPSTREAM_DIR / "acme" / "widget.git"
        assert worktree_path(url) == paths.UPSTREAM_DIR / "acme" / "widget"


class TestListUpstreams:
    """#COPR-0004: the registry is derived from packages.yaml urls."""

    def test_dedupes_by_url_and_sorts(self, upstream_repo):
        packages = {
            "b": {"url": "https://github.com/z/zed"},
            "a": {"url": "https://github.com/acme/widget"},
            "a-git": {"url": "https://github.com/acme/widget"},
            "no-url": {"description": "x"},
        }
        mods = list_upstreams(packages)
        assert [m["url"] for m in mods] == [
            "https://github.com/acme/widget",
            "https://github.com/z/zed",
        ]
        assert mods[0]["name"] == "acme/widget"
        assert mods[0]["path"] == ".cache/upstream/acme/widget"

    def test_empty_packages(self, upstream_repo):
        assert list_upstreams({}) == []


class TestFindUpstream:
    """#COPR-0004: look a cached mirror up by name (scaffold-package PACKAGE=)."""

    def test_finds_cached_mirror_by_last_component(self, upstream_repo):
        ensure_mirror(upstream_repo["url"])
        found = find_upstream("widget")
        assert found is not None
        assert found["name"] == "acme/widget"

    def test_missing_returns_none(self, upstream_repo):
        assert find_upstream("nothing") is None


class TestEnsureMirror:
    """#COPR-0004: bare mirror creation and self-heal (real git)."""

    def test_first_call_creates_bare_mirror_with_refspecs(self, upstream_repo):
        assert ensure_mirror(upstream_repo["url"]) is None
        mirror = mirror_path(upstream_repo["url"])
        assert _git("rev-parse", "--is-bare-repository", cwd=mirror) == "true"
        refspecs = _git("config", "--get-all", "remote.origin.fetch", cwd=mirror)
        assert "+refs/heads/*:refs/remotes/origin/*" in refspecs
        assert "+refs/tags/*:refs/tags/*" in refspecs

    def test_second_call_is_noop(self, upstream_repo):
        ensure_mirror(upstream_repo["url"])
        marker = mirror_path(upstream_repo["url"]) / "marker"
        marker.write_text("x")
        assert ensure_mirror(upstream_repo["url"]) is None
        assert marker.exists()

    def test_corrupt_mirror_is_recreated(self, upstream_repo):
        ensure_mirror(upstream_repo["url"])
        mirror = mirror_path(upstream_repo["url"])
        (mirror / "HEAD").unlink()
        assert ensure_mirror(upstream_repo["url"]) is None
        assert _git("rev-parse", "--is-bare-repository", cwd=mirror) == "true"


class TestFetchMirror:
    """#COPR-0004: fetch tags + branches, set origin/HEAD."""

    def test_fetch_populates_branches_tags_and_head(self, upstream_repo):
        assert fetch_mirror(upstream_repo["url"]) is None
        mirror = mirror_path(upstream_repo["url"])
        assert _git("rev-parse", "origin/main", cwd=mirror) == upstream_repo["second"]
        assert (
            _git("rev-parse", "refs/tags/v1.0.0^{commit}", cwd=mirror)
            == upstream_repo["first"]
        )
        assert (
            _git("symbolic-ref", "refs/remotes/origin/HEAD", cwd=mirror)
            == "refs/remotes/origin/main"
        )

    def test_fetch_failure_returns_error_and_keeps_mirror(
        self, upstream_repo, tmp_path
    ):
        fetch_mirror(upstream_repo["url"])
        mirror = mirror_path(upstream_repo["url"])
        _git("remote", "set-url", "origin", (tmp_path / "gone").as_uri(), cwd=mirror)
        err = fetch_mirror(upstream_repo["url"])
        assert err
        assert mirror.exists()

    def test_prune_drops_deleted_tag(self, upstream_repo):
        fetch_mirror(upstream_repo["url"])
        _git("tag", "-d", "v1.0.0", cwd=upstream_repo["path"])
        fetch_mirror(upstream_repo["url"])
        mirror = mirror_path(upstream_repo["url"])
        assert "v1.0.0" not in _git("tag", "-l", cwd=mirror).split()


class TestCheckoutWorktree:
    """#COPR-0004: detached, relative-path, never-dirty worktree."""

    def test_creates_detached_worktree_with_relative_gitdir(self, upstream_repo):
        fetch_mirror(upstream_repo["url"])
        assert checkout_worktree(upstream_repo["url"], "origin/main") is None
        wt = worktree_path(upstream_repo["url"])
        assert (wt / "meson.build").exists()
        assert _git("rev-parse", "HEAD", cwd=wt) == upstream_repo["second"]
        head = subprocess.run(
            ["git", "symbolic-ref", "-q", "HEAD"], cwd=wt, capture_output=True
        )
        assert head.returncode != 0  # detached
        gitfile = (wt / ".git").read_text().strip()
        assert gitfile.startswith("gitdir: ..")

    def test_moves_to_pinned_tag(self, upstream_repo):
        fetch_mirror(upstream_repo["url"])
        checkout_worktree(upstream_repo["url"], "origin/main")
        assert checkout_worktree(upstream_repo["url"], "refs/tags/v1.0.0") is None
        wt = worktree_path(upstream_repo["url"])
        assert _git("rev-parse", "HEAD", cwd=wt) == upstream_repo["first"]

    def test_moves_to_pinned_commit(self, upstream_repo):
        fetch_mirror(upstream_repo["url"])
        assert checkout_worktree(upstream_repo["url"], upstream_repo["first"]) is None
        wt = worktree_path(upstream_repo["url"])
        assert _git("rev-parse", "HEAD", cwd=wt) == upstream_repo["first"]

    def test_dirty_worktree_is_reset(self, upstream_repo):
        fetch_mirror(upstream_repo["url"])
        checkout_worktree(upstream_repo["url"], "origin/main")
        wt = worktree_path(upstream_repo["url"])
        (wt / "stray.txt").write_text("junk")
        (wt / "meson.build").write_text("tampered")
        assert checkout_worktree(upstream_repo["url"], "origin/main") is None
        assert not (wt / "stray.txt").exists()
        assert _git("status", "--porcelain", cwd=wt) == ""

    def test_deleted_worktree_dir_is_recreated(self, upstream_repo):
        import shutil

        fetch_mirror(upstream_repo["url"])
        checkout_worktree(upstream_repo["url"], "origin/main")
        shutil.rmtree(worktree_path(upstream_repo["url"]))
        assert checkout_worktree(upstream_repo["url"], "origin/main") is None
        assert (worktree_path(upstream_repo["url"]) / "meson.build").exists()

    def test_unknown_ref_returns_error(self, upstream_repo):
        fetch_mirror(upstream_repo["url"])
        assert checkout_worktree(upstream_repo["url"], "refs/tags/nope")


class TestSyncUpstream:
    """#COPR-0004: clone/fetch/checkout in one call."""

    def test_sync_from_nothing_defaults_to_origin_head(self, upstream_repo):
        wt = sync_upstream(upstream_repo["url"])
        assert wt == worktree_path(upstream_repo["url"])
        assert _git("rev-parse", "HEAD", cwd=wt) == upstream_repo["second"]

    def test_sync_with_ref(self, upstream_repo):
        wt = sync_upstream(upstream_repo["url"], "refs/tags/v1.0.0")
        assert _git("rev-parse", "HEAD", cwd=wt) == upstream_repo["first"]

    def test_sync_picks_up_new_upstream_commit(self, upstream_repo):
        sync_upstream(upstream_repo["url"])
        origin = upstream_repo["path"]
        (origin / "new.txt").write_text("n")
        _git("add", ".", cwd=origin)
        _git("commit", "-qm", "third", cwd=origin)
        third = _git("rev-parse", "HEAD", cwd=origin)
        wt = sync_upstream(upstream_repo["url"])
        assert _git("rev-parse", "HEAD", cwd=wt) == third

    def test_sync_unreachable_origin_raises(self, upstream_repo, tmp_path):
        with pytest.raises(UpstreamError):
            sync_upstream((tmp_path / "gone").as_uri())

    def test_metadata_helpers_work_on_the_worktree(self, upstream_repo):
        wt = sync_upstream(upstream_repo["url"])
        commit = get_tag_commit(wt, "v1.0.0")
        assert commit is not None
        assert commit[0] == upstream_repo["first"]
        info = get_changelog_info(wt, "1.1.0", None)
        assert info is not None
