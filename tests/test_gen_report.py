"""Tests for gen-report.py script (#COPR-0012)."""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

gen_report = importlib.import_module("gen-report")


class TestCollectGroups:
    """collect_groups builds the README package list from yaml alone."""

    def test_package_listed_with_summary_from_packages_yaml(self):
        groups = gen_report.collect_groups(
            {"apps": {"label": "Apps", "packages": ["foo"]}},
            {"foo": {"summary": "Foo thing"}},
        )
        assert groups == [
            {
                "label": "Apps",
                "badge": None,
                "packages": [{"name": "foo", "summary": "Foo thing"}],
            }
        ]

    def test_package_missing_from_packages_yaml_is_skipped(self):
        groups = gen_report.collect_groups(
            {"apps": {"packages": ["foo", "ghost"]}},
            {"foo": {"summary": "Foo thing"}},
        )
        assert [p["name"] for p in groups[0]["packages"]] == ["foo"]

    def test_package_without_summary_gets_empty_summary(self):
        groups = gen_report.collect_groups(
            {"apps": {"packages": ["foo"]}}, {"foo": {}}
        )
        assert groups[0]["packages"][0]["summary"] == ""

    def test_global_repo_packages_are_kept_as_given(self):
        groups = gen_report.collect_groups(
            {
                "apps": {
                    "packages": [],
                    "packages_from_global_repo": [
                        {"name": "fuzzel", "summary": "Launcher"},
                        "not-a-dict-is-ignored",
                    ],
                }
            },
            {},
        )
        assert groups[0]["packages"] == [{"name": "fuzzel", "summary": "Launcher"}]

    def test_group_order_label_default_and_badge_passthrough(self):
        badge = {"logo": "fedora", "color": "blue", "logo_color": "white"}
        groups = gen_report.collect_groups(
            {"b": {"packages": []}, "a": {"label": "A", "badge": badge}}, {}
        )
        assert [g["label"] for g in groups] == ["b", "A"]
        assert groups[1]["badge"] == badge

    def test_group_without_packages_key_is_empty(self):
        groups = gen_report.collect_groups({"a": {"label": "A"}}, {})
        assert groups[0]["packages"] == []


class TestMain:
    """main() renders the requested templates with yaml-derived context only."""

    @pytest.fixture
    def env(self, tmp_path):
        """Patch every input main() reads and return the fake Jinja env."""
        template = MagicMock()
        template.render.return_value = "Generated output"
        jinja_env = MagicMock()
        jinja_env.get_template.return_value = template
        with (
            patch.object(gen_report, "PACKAGES_YAML", tmp_path / "packages.yaml"),
            patch.object(gen_report, "REPO_YAML", tmp_path / "repo.yaml"),
            patch.object(gen_report, "GROUPS_YAML", tmp_path / "groups.yaml"),
            patch.object(gen_report, "ROOT", tmp_path),
            patch.object(gen_report, "create_jinja_env", return_value=jinja_env),
        ):
            yield jinja_env

    def _run(self, *argv):
        with patch("sys.argv", ["gen-report.py", *argv]):
            gen_report.main()

    def test_writes_to_stdout_by_default(self, env, capsys):
        self._run()
        assert "Generated output" in capsys.readouterr().out
        env.get_template.assert_called_once_with("readme-github.md.j2")

    def test_writes_to_file_with_output_arg(self, env, tmp_path):
        out = tmp_path / "README.md"
        self._run("--format", "github", "--output", str(out))
        assert out.read_text() == "Generated output"

    def test_selects_copr_template(self, env, capsys):
        self._run("--format", "copr")
        env.get_template.assert_called_once_with("readme-copr.md.j2")

    def test_renders_multiple_formats_from_one_invocation(self, env, tmp_path):
        """Repeated --format/--output pairs (TODO-0067) render every template
        from a single read of the inputs, each to its own output file."""
        env.get_template.return_value.render.side_effect = ["github-out", "copr-out"]
        out_github = tmp_path / "README.md"
        out_copr = tmp_path / "README.copr.md"
        self._run(
            "--format", "github", "--output", str(out_github),
            "--format", "copr", "--output", str(out_copr),
        )
        assert out_github.read_text() == "github-out"
        assert out_copr.read_text() == "copr-out"
        assert [c.args for c in env.get_template.call_args_list] == [
            ("readme-github.md.j2",),
            ("readme-copr.md.j2",),
        ]

    def test_rejects_mismatched_format_output_counts(self, env, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            self._run(
                "--format", "github", "--format", "copr",
                "--output", str(tmp_path / "x"),
            )
        assert exc_info.value.code == 2

    @pytest.mark.parametrize("fmt", ["full-report", "nope"])
    def test_rejects_unknown_and_removed_formats(self, env, fmt):
        with pytest.raises(SystemExit) as exc_info:
            self._run("--format", fmt)
        assert exc_info.value.code == 2

    @pytest.mark.parametrize("flag", [["--skip-copr-poll"], ["--db-snapshot", "x"]])
    def test_rejects_removed_flags(self, env, flag):
        with pytest.raises(SystemExit) as exc_info:
            self._run(*flag)
        assert exc_info.value.code == 2

    def test_render_context_has_no_build_state(self, env):
        self._run()
        context = env.get_template.return_value.render.call_args.kwargs
        assert set(context) == {
            "repo",
            "groups",
            "contributors",
            "badge_style",
            "news_entries",
            "sections",
        }

    def test_does_not_use_build_db_or_copr(self):
        assert not hasattr(gen_report, "build_db")
        assert not hasattr(gen_report, "poll_copr_status")
