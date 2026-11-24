"""The Hyprland spec stamps its build with the real tag commit (hyprpm needs it)."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.yaml_utils import get_packages  # noqa: E402

stage_spec = importlib.import_module("scripts.stage-spec")


def _spec() -> str:
    packages = get_packages()
    return stage_spec.generate_spec("Hyprland", packages["Hyprland"], packages, "44")


def _section(spec: str, start: str, end: str) -> str:
    return spec.split(start, 1)[1].split(end, 1)[0]


class TestHyprlandCommitEnv:
    def test_commit_hash_is_read_from_the_source_tarball_before_cmake(self):
        build = _section(_spec(), "%build", "%install")
        assert "GIT_COMMIT_HASH=$(gzip -dc %{SOURCE0} | git get-tar-commit-id)" in build
        assert build.index("GIT_COMMIT_HASH") < build.index("%cmake")

    def test_build_fails_when_the_hash_is_empty(self):
        build = _section(_spec(), "%build", "%install")
        assert 'test -n "$GIT_COMMIT_HASH"' in build
        assert build.index('test -n "$GIT_COMMIT_HASH"') < build.index("%cmake")

    def test_tag_and_clean_tree_are_stamped(self):
        build = _section(_spec(), "%build", "%install")
        assert "export GIT_TAG=v%{version}" in build
        assert "export GIT_DIRTY=clean" in build

    def test_git_is_a_build_requirement(self):
        header = _spec().split("%description", 1)[0]
        assert "BuildRequires:  git-core" in header

    def test_branch_message_count_and_date_are_stamped(self):
        """#COPR-0031"""
        build = _section(_spec(), "%build", "%install")
        assert "export GIT_BRANCH=v%{version}" in build
        assert 'export GIT_COMMIT_MESSAGE="%{?upstream_commit_subject}"' in build
        assert "export GIT_COMMITS=%{?upstream_commits}" in build
        assert "export GIT_COMMIT_DATE=" in build
        assert "%{SOURCE0}" in build.split("export GIT_COMMIT_DATE=", 1)[1].split("\n")[0]
        assert 'test -n "$GIT_COMMIT_DATE"' in build
        for name in ("GIT_BRANCH", "GIT_COMMIT_MESSAGE", "GIT_COMMITS", "GIT_COMMIT_DATE"):
            assert build.index(name) < build.index("%cmake")
