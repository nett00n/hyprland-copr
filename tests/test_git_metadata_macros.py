"""#COPR-0031: stage-spec emits upstream commit subject/count macros."""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.yaml_utils import get_packages  # noqa: E402

stage_spec = importlib.import_module("scripts.stage-spec")


def _spec(info):
    packages = get_packages()
    with patch.object(stage_spec, "get_changelog_info", return_value=info):
        return stage_spec.generate_spec(
            "Hyprland", packages["Hyprland"], packages, "44"
        )


def _info(**extra):
    base = {
        "published_at": "2026-11-09T15:05:46+00:00",
        "body": "x",
        "tag": "v0.57.2",
        "commit": "11cbc6c577b84ffb1edf4df3fc5b6128c3ae6947",
    }
    return {**base, **extra}


class TestGitMetadataMacros:
    def test_globals_rendered(self):
        spec = _spec(_info(subject="VERSION: bump to 0.57.2", commits=8015))
        assert "%global upstream_commit_subject VERSION: bump to 0.57.2\n" in spec
        assert "%global upstream_commits 8015\n" in spec

    def test_subject_is_sanitized(self):
        spec = _spec(_info(subject='50% "quoted" back\\slash\x07', commits=1))
        line = next(
            ln
            for ln in spec.splitlines()
            if ln.startswith("%global upstream_commit_subject")
        )
        assert line == "%global upstream_commit_subject 50%% 'quoted' backslash"

    def test_omitted_without_info(self):
        spec = _spec(None)
        assert "upstream_commit_subject" not in spec.split("%build", 1)[0]
        assert "%global upstream_commits" not in spec

    def test_omitted_when_fields_missing(self):
        spec = _spec(_info())
        assert "%global upstream_commits" not in spec
