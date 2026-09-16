"""Tests for scripts/gen-readme-shell.py. #BUG-0078

Splices rendered header/footer templates into README.md/docs/README.copr.md
between BEGIN/END marker comments, leaving the body (packages table, build
status) untouched. Everything runs under tmp_path with ROOT/REPO_YAML
monkeypatched -- never against the real repo files.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

gen_readme_shell = importlib.import_module("scripts.gen-readme-shell")

main = gen_readme_shell.main


class _FakeTemplate:
    def __init__(self, text):
        self._text = text

    def render(self, **_context):
        return self._text


class _FakeEnv:
    def get_template(self, name):
        if name == "__header.j2":
            return _FakeTemplate("<!-- rendered header -->")
        if name == "__footer.j2":
            return _FakeTemplate("<!-- rendered footer -->")
        raise AssertionError(f"unexpected template: {name}")


def _target_text(body="THE PACKAGES TABLE, UNTOUCHED"):
    return (
        "<!-- BEGIN: Header -->\nold header\n<!-- END: Header -->\n\n"
        f"{body}\n\n"
        "<!-- BEGIN: Footer -->\nold footer\n<!-- END: Footer -->\n"
    )


def _setup(tmp_path, monkeypatch, targets_content):
    """Write repo.yaml + each target file, monkeypatch ROOT/REPO_YAML/TARGETS."""
    monkeypatch.setattr(gen_readme_shell, "ROOT", tmp_path)
    monkeypatch.setattr(gen_readme_shell, "REPO_YAML", tmp_path / "repo.yaml")
    (tmp_path / "repo.yaml").write_text("name: test-repo\n")
    for rel_path, content in targets_content.items():
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


class TestMain:
    def test_splices_header_and_footer_leaving_body_untouched(
        self, tmp_path, monkeypatch, capsys
    ):
        _setup(
            tmp_path,
            monkeypatch,
            {
                "README.md": _target_text(),
                "docs/README.copr.md": _target_text(),
            },
        )
        with (
            patch.object(gen_readme_shell, "create_jinja_env", return_value=_FakeEnv()),
            patch.object(gen_readme_shell, "load_repo_yaml", return_value={}),
            patch.object(gen_readme_shell, "collect_contributors", return_value=[]),
            patch.object(gen_readme_shell, "get_recent_news", return_value=[]),
            patch.object(gen_readme_shell, "get_sections", return_value={}),
        ):
            main()

        new_text = (tmp_path / "README.md").read_text()
        assert "<!-- rendered header -->" in new_text
        assert "<!-- rendered footer -->" in new_text
        assert "old header" not in new_text
        assert "old footer" not in new_text
        assert "THE PACKAGES TABLE, UNTOUCHED" in new_text

        out = capsys.readouterr().out
        assert "updated: README.md" in out
        assert "updated: docs/README.copr.md" in out

    def test_missing_repo_yaml_exits(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gen_readme_shell, "ROOT", tmp_path)
        monkeypatch.setattr(gen_readme_shell, "REPO_YAML", tmp_path / "repo.yaml")

        raised = False
        try:
            main()
        except SystemExit as exc:
            raised = True
            assert exc.code == 1
        assert raised

    def test_missing_target_file_is_skipped(self, tmp_path, monkeypatch, capsys):
        _setup(tmp_path, monkeypatch, {"README.md": _target_text()})
        # docs/README.copr.md deliberately not created

        with (
            patch.object(gen_readme_shell, "create_jinja_env", return_value=_FakeEnv()),
            patch.object(gen_readme_shell, "load_repo_yaml", return_value={}),
            patch.object(gen_readme_shell, "collect_contributors", return_value=[]),
            patch.object(gen_readme_shell, "get_recent_news", return_value=[]),
            patch.object(gen_readme_shell, "get_sections", return_value={}),
        ):
            main()

        out, err = capsys.readouterr()
        assert "skip (missing): docs/README.copr.md" in err
        assert "updated: README.md" in out

    def test_missing_markers_is_skipped_and_file_untouched(
        self, tmp_path, monkeypatch, capsys
    ):
        no_markers = "just some content\nwith no marker comments at all\n"
        _setup(
            tmp_path,
            monkeypatch,
            {"README.md": no_markers, "docs/README.copr.md": _target_text()},
        )

        with (
            patch.object(gen_readme_shell, "create_jinja_env", return_value=_FakeEnv()),
            patch.object(gen_readme_shell, "load_repo_yaml", return_value={}),
            patch.object(gen_readme_shell, "collect_contributors", return_value=[]),
            patch.object(gen_readme_shell, "get_recent_news", return_value=[]),
            patch.object(gen_readme_shell, "get_sections", return_value={}),
        ):
            main()

        assert (tmp_path / "README.md").read_text() == no_markers
        out, err = capsys.readouterr()
        assert "skip (no BEGIN/END markers found): README.md" in err

    def test_unchanged_content_reports_unchanged(self, tmp_path, monkeypatch, capsys):
        """Re-splicing identical header/footer text reports 'unchanged'."""
        target = _target_text()
        _setup(
            tmp_path, monkeypatch, {"README.md": target, "docs/README.copr.md": target}
        )

        class _IdentityEnv:
            def get_template(self, name):
                if name == "__header.j2":
                    return _FakeTemplate("<!-- BEGIN: Header -->\nold header\n<!-- END: Header -->")
                if name == "__footer.j2":
                    return _FakeTemplate("<!-- BEGIN: Footer -->\nold footer\n<!-- END: Footer -->")
                raise AssertionError(name)

        with (
            patch.object(gen_readme_shell, "create_jinja_env", return_value=_IdentityEnv()),
            patch.object(gen_readme_shell, "load_repo_yaml", return_value={}),
            patch.object(gen_readme_shell, "collect_contributors", return_value=[]),
            patch.object(gen_readme_shell, "get_recent_news", return_value=[]),
            patch.object(gen_readme_shell, "get_sections", return_value={}),
        ):
            main()

        out = capsys.readouterr().out
        assert "unchanged: README.md" in out
        assert "unchanged: docs/README.copr.md" in out
