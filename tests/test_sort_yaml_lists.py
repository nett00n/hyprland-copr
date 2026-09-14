"""Tests for scripts/sort-yaml-lists.py.

sort-yaml-lists.py rewrites packages.yaml -- the repo's source of truth --
in place. process_content() is a pure str -> str function so it is exercised
directly, with real packages.yaml round-tripped through it as the strongest
single regression check.
"""

import importlib
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

sort_yaml_lists = importlib.import_module("scripts.sort-yaml-lists")

process_content = sort_yaml_lists.process_content
_sort_block = sort_yaml_lists._sort_block
_item_sort_key = sort_yaml_lists._item_sort_key

REAL_PACKAGES_YAML = Path(__file__).parent.parent / "packages.yaml"


class TestItemSortKey:
    def test_strips_list_prefix_and_quotes(self):
        assert _item_sort_key('  - "Foo"') == "foo"
        assert _item_sort_key("  - 'Foo'") == "foo"
        assert _item_sort_key("  - Foo") == "foo"

    def test_case_insensitive(self):
        assert _item_sort_key("- Foo") == _item_sort_key("- foo")


class TestSortBlock:
    def test_alphabetical_sort(self):
        lines = ["  - zeta\n", "  - alpha\n", "  - mu\n"]
        assert _sort_block(lines) == ["  - alpha\n", "  - mu\n", "  - zeta\n"]

    def test_case_insensitive_ordering(self):
        lines = ["  - Zeta\n", "  - alpha\n"]
        assert _sort_block(lines) == ["  - alpha\n", "  - Zeta\n"]

    def test_dedup_exact_duplicates(self):
        lines = ["  - foo\n", "  - foo\n", "  - bar\n"]
        result = _sort_block(lines)
        assert result == ["  - bar\n", "  - foo\n"]

    def test_dedup_case_differing_duplicates_keeps_first_spelling(self):
        lines = ["  - Foo\n", "  - foo\n"]
        result = _sort_block(lines)
        assert result == ["  - Foo\n"]

    def test_comments_float_to_top(self):
        lines = ["  - zeta\n", "  # a comment\n", "  - alpha\n"]
        result = _sort_block(lines)
        assert result[0] == "  # a comment\n"
        assert result[1:] == ["  - alpha\n", "  - zeta\n"]


class TestProcessContentListSorting:
    def test_sorts_build_requires(self):
        content = "pkg:\n  build_requires:\n    - zeta\n    - alpha\n"
        new_content, sorted_keys = process_content(content)
        assert "alpha" in new_content.split("zeta")[0]
        assert sorted_keys == ["build_requires"]

    def test_already_sorted_reports_no_change(self):
        content = "pkg:\n  build_requires:\n    - alpha\n    - zeta\n"
        new_content, sorted_keys = process_content(content)
        assert new_content == content
        assert sorted_keys == []

    def test_dedups_requires_list(self):
        content = "pkg:\n  requires:\n    - foo\n    - foo\n"
        new_content, _ = process_content(content)
        assert new_content.count("foo") == 1


class TestProcessContentDictSorting:
    def test_sorts_dict_keys_within_mapping(self):
        content = "pkg:\n  zeta_key: 1\n  alpha_key: 2\n"
        new_content, sorted_keys = process_content(content)
        assert new_content.index("alpha_key") < new_content.index("zeta_key")
        assert "dict" in sorted_keys

    def test_sorts_top_level_package_names(self):
        content = "zeta-pkg:\n  version: \"1\"\nalpha-pkg:\n  version: \"1\"\n"
        new_content, sorted_keys = process_content(content)
        assert new_content.index("alpha-pkg") < new_content.index("zeta-pkg")
        assert "dict" in sorted_keys

    def test_leading_document_marker_preserved_and_excluded_from_sort(self):
        content = '---\nzeta-pkg:\n  version: "1"\nalpha-pkg:\n  version: "1"\n'
        new_content, _ = process_content(content)
        assert new_content.startswith("---\n")
        assert new_content.index("alpha-pkg") < new_content.index("zeta-pkg")

    def test_recurses_into_nested_dicts(self):
        content = "pkg:\n  source:\n    zeta: 1\n    alpha: 2\n"
        new_content, _ = process_content(content)
        assert new_content.index("alpha") < new_content.index("zeta")

    def test_list_of_dicts_left_untouched(self):
        """sources/bundled_deps are lists of dicts -- documented non-goal."""
        content = (
            "pkg:\n"
            "  sources:\n"
            "    - url: zeta-url\n"
            "      name: z\n"
            "    - url: alpha-url\n"
            "      name: a\n"
        )
        new_content, sorted_keys = process_content(content)
        assert new_content == content
        assert sorted_keys == []


class TestBlockCollection:
    def test_blank_lines_inside_block_scalar_kept_in_body(self):
        content = (
            "pkg:\n"
            "  zeta_key: 1\n"
            "  description: |\n"
            "    line one\n"
            "\n"
            "    line two\n"
            "  alpha_key: 2\n"
        )
        new_content, _ = process_content(content)
        # The blank line inside the block scalar must survive the sort.
        assert "line one\n\n    line two" in new_content

    def test_trailing_blank_lines_emitted_after_sorted_body(self):
        """Trailing blanks stay attached right after their entry's sorted
        content -- verified with a single top-level entry so top-level
        reordering (which carries a trailing blank along with whichever
        entry it's attached to) can't also move them."""
        content = "pkg:\n  zeta_key: 1\n  alpha_key: 2\n\n\n"
        new_content, _ = process_content(content)
        assert new_content == "pkg:\n  alpha_key: 2\n  zeta_key: 1\n\n\n"


class TestIdempotence:
    def test_double_pass_is_stable(self):
        content = (
            "zeta-pkg:\n"
            "  build_requires:\n"
            "    - zeta\n"
            "    - alpha\n"
            "  zeta_key: 1\n"
            "  alpha_key: 2\n"
            "alpha-pkg:\n"
            "  version: \"1\"\n"
        )
        first_pass, _ = process_content(content)
        second_pass, sorted_keys_2 = process_content(first_pass)
        assert second_pass == first_pass
        assert sorted_keys_2 == []

    def test_real_packages_yaml_is_idempotent(self):
        """The strongest available assertion: sorting the actual source of
        truth twice must converge, and (if already sorted, as it should be
        after `make fmt`) the first pass should also be a no-op."""
        if not REAL_PACKAGES_YAML.exists():
            pytest.skip("packages.yaml not present in this checkout")
        content = REAL_PACKAGES_YAML.read_text()
        first_pass, _ = process_content(content)
        second_pass, sorted_keys_2 = process_content(first_pass)
        assert second_pass == first_pass
        assert sorted_keys_2 == []


def _canon(obj):
    """Canonicalize for semantic comparison: dict key order never matters,
    and a list of plain strings (build_requires/requires/files) is
    intentionally reordered by sorting, so compare it as a set-like sorted
    list. A list of dicts (sources, bundled_deps) is left untouched by the
    tool, so its order is preserved and must still match exactly.
    """
    if isinstance(obj, dict):
        return {k: _canon(v) for k, v in obj.items()}
    if isinstance(obj, list):
        if all(isinstance(x, str) for x in obj):
            return sorted(obj, key=str.lower)
        return [_canon(x) for x in obj]
    return obj


class TestRoundTrip:
    def test_semantic_content_unchanged_by_sorting(self):
        content = (
            "zeta-pkg:\n"
            "  version: \"1.0\"\n"
            "  build_requires:\n"
            "    - zeta\n"
            "    - alpha\n"
            "  sources:\n"
            "    - url: b\n"
            "    - url: a\n"
        )
        new_content, _ = process_content(content)
        assert _canon(yaml.safe_load(new_content)) == _canon(yaml.safe_load(content))

    def test_real_packages_yaml_round_trips(self):
        if not REAL_PACKAGES_YAML.exists():
            pytest.skip("packages.yaml not present in this checkout")
        content = REAL_PACKAGES_YAML.read_text()
        new_content, _ = process_content(content)
        assert _canon(yaml.safe_load(new_content)) == _canon(yaml.safe_load(content))


class TestMainCli:
    def test_dry_run_writes_nothing_and_prefixes_output(self, tmp_path, monkeypatch, capsys):
        pkg_yaml = tmp_path / "packages.yaml"
        pkg_yaml.write_text("pkg:\n  build_requires:\n    - zeta\n    - alpha\n")
        monkeypatch.setattr(sort_yaml_lists, "PACKAGES_YAML", pkg_yaml)
        monkeypatch.setattr(sort_yaml_lists, "ROOT", tmp_path)
        monkeypatch.setattr(sys, "argv", ["sort-yaml-lists.py", "--dry-run"])
        original = pkg_yaml.read_text()

        sort_yaml_lists.main()

        assert pkg_yaml.read_text() == original
        out = capsys.readouterr().out
        assert out.startswith("[dry-run] ")

    def test_already_sorted_prints_nothing_to_sort(self, tmp_path, monkeypatch, capsys):
        pkg_yaml = tmp_path / "packages.yaml"
        pkg_yaml.write_text("pkg:\n  build_requires:\n    - alpha\n    - zeta\n")
        monkeypatch.setattr(sort_yaml_lists, "PACKAGES_YAML", pkg_yaml)
        monkeypatch.setattr(sort_yaml_lists, "ROOT", tmp_path)
        monkeypatch.setattr(sys, "argv", ["sort-yaml-lists.py"])

        sort_yaml_lists.main()

        assert "Nothing to sort" in capsys.readouterr().out

    def test_missing_packages_yaml_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sort_yaml_lists, "PACKAGES_YAML", tmp_path / "missing.yaml")
        monkeypatch.setattr(sort_yaml_lists, "ROOT", tmp_path)
        monkeypatch.setattr(sys, "argv", ["sort-yaml-lists.py"])

        with pytest.raises(SystemExit):
            sort_yaml_lists.main()

    def test_writes_sorted_content_and_reports_counts(self, tmp_path, monkeypatch, capsys):
        pkg_yaml = tmp_path / "packages.yaml"
        pkg_yaml.write_text("pkg:\n  build_requires:\n    - zeta\n    - alpha\n")
        monkeypatch.setattr(sort_yaml_lists, "PACKAGES_YAML", pkg_yaml)
        monkeypatch.setattr(sort_yaml_lists, "ROOT", tmp_path)
        monkeypatch.setattr(sys, "argv", ["sort-yaml-lists.py"])

        sort_yaml_lists.main()

        assert "alpha" in pkg_yaml.read_text().split("zeta")[0]
        assert "Sorted 1 block(s)" in capsys.readouterr().out
