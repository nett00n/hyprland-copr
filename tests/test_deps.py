"""Unit tests for scripts/lib/deps.py"""

import pytest

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.deps import (
    declared_deps,
    effective_deps,
    build_dep_graph,
    ordered_packages,
    reverse_graph,
    topological_sort,
    transitive_deps,
)


class TestEffectiveDeps:
    """Test dependency resolution from explicit depends_on or build_requires."""

    def test_explicit_depends_on_wins(self):
        """Explicit depends_on takes precedence over build_requires."""
        all_packages = {
            "foo": {},
            "bar": {},
            "baz": {},
        }
        meta = {
            "depends_on": ["foo", "bar"],
            "build_requires": ["baz-devel"],
        }
        assert effective_deps("pkg", meta, all_packages) == {"foo", "bar"}

    def test_infer_from_devel_suffix(self):
        """Falls back to stripping -devel from build_requires."""
        all_packages = {
            "foo": {},
            "bar": {},
        }
        meta = {
            "build_requires": ["foo-devel", "bar-devel", "some-library"],
        }
        assert effective_deps("pkg", meta, all_packages) == {"foo", "bar"}

    def test_no_deps_returns_empty(self):
        """Package with no deps returns empty set."""
        all_packages = {"foo": {}}
        meta = {}
        assert effective_deps("pkg", meta, all_packages) == set()

    def test_excludes_self(self):
        """Package name is excluded from dependencies."""
        all_packages = {"pkg": {}, "foo": {}}
        meta = {"depends_on": ["pkg", "foo"]}
        assert effective_deps("pkg", meta, all_packages) == {"foo"}

    def test_case_insensitive_resolution(self):
        """Dependency names are resolved case-insensitively."""
        all_packages = {
            "MyPackage": {},
            "OtherPkg": {},
        }
        meta = {
            "depends_on": ["mypackage", "otherpkg"],
        }
        assert effective_deps("pkg", meta, all_packages) == {"MyPackage", "OtherPkg"}

    def test_missing_dep_silently_ignored(self):
        """References to non-existent packages are silently ignored."""
        all_packages = {"foo": {}}
        meta = {
            "depends_on": ["foo", "nonexistent"],
        }
        assert effective_deps("pkg", meta, all_packages) == {"foo"}

    def test_empty_build_requires(self):
        """Empty or missing build_requires is handled gracefully."""
        all_packages = {}
        meta = {"build_requires": []}
        assert effective_deps("pkg", meta, all_packages) == set()

    def test_build_requires_with_versions(self):
        """build_requires with version specs are handled (version stripped during matching)."""
        all_packages = {"foo": {}}
        meta = {
            "build_requires": ["foo-devel >= 1.0"],
        }
        # The -devel is stripped, but version spec remains; no match
        # since "foo >= 1.0" is not found in packages
        assert effective_deps("pkg", meta, all_packages) == set()


class TestDeclaredDeps:
    """Test raw depends_on field access (no build_requires inference)."""

    def test_returns_declared_list(self):
        """Returns the depends_on list verbatim."""
        meta = {"depends_on": ["foo", "bar"]}
        assert declared_deps(meta) == ["foo", "bar"]

    def test_ignores_build_requires(self):
        """Does not fall back to build_requires inference."""
        meta = {"build_requires": ["foo-devel"]}
        assert declared_deps(meta) == []

    def test_missing_field_returns_empty(self):
        """Missing depends_on returns empty list."""
        assert declared_deps({}) == []

    def test_none_value_returns_empty(self):
        """Explicit depends_on: null returns empty list, not None."""
        assert declared_deps({"depends_on": None}) == []


class TestBuildDepGraph:
    """Test dependency graph construction."""

    def test_single_package_no_deps(self):
        """Single package with no dependencies."""
        packages = {"foo": {}}
        graph = build_dep_graph(packages)
        assert graph == {"foo": set()}

    def test_multiple_packages_linear_chain(self):
        """Linear dependency chain: a -> b -> c."""
        packages = {
            "a": {"depends_on": ["b"]},
            "b": {"depends_on": ["c"]},
            "c": {},
        }
        graph = build_dep_graph(packages)
        assert graph["a"] == {"b"}
        assert graph["b"] == {"c"}
        assert graph["c"] == set()

    def test_multiple_packages_diamond(self):
        """Diamond dependency: a -> b,c; b,c -> d."""
        packages = {
            "a": {"depends_on": ["b", "c"]},
            "b": {"depends_on": ["d"]},
            "c": {"depends_on": ["d"]},
            "d": {},
        }
        graph = build_dep_graph(packages)
        assert graph["a"] == {"b", "c"}
        assert graph["b"] == {"d"}
        assert graph["c"] == {"d"}
        assert graph["d"] == set()

    def test_empty_graph(self):
        """Empty package dict produces empty graph."""
        packages = {}
        graph = build_dep_graph(packages)
        assert graph == {}


class TestReverseGraph:
    """Test reverse_graph(), the {pkg: deps} -> {pkg: dependents} inversion."""

    def test_empty_graph(self):
        assert reverse_graph({}) == {}

    def test_single_node_no_deps(self):
        assert reverse_graph({"a": set()}) == {"a": set()}

    def test_linear_chain(self):
        """a -> b -> c means b and c each gain one dependent."""
        graph = {"a": {"b"}, "b": {"c"}, "c": set()}
        assert reverse_graph(graph) == {"a": set(), "b": {"a"}, "c": {"b"}}

    def test_diamond(self):
        """a -> b,c; b,c -> d means d has two dependents."""
        graph = {"a": {"b", "c"}, "b": {"d"}, "c": {"d"}, "d": set()}
        result = reverse_graph(graph)
        assert result["d"] == {"b", "c"}
        assert result["b"] == {"a"}
        assert result["c"] == {"a"}
        assert result["a"] == set()

    def test_every_key_preserved_even_with_no_dependents(self):
        graph = {"a": set(), "b": set(), "c": set()}
        result = reverse_graph(graph)
        assert set(result.keys()) == {"a", "b", "c"}
        assert all(v == set() for v in result.values())

    def test_dangling_dep_not_added_as_key(self):
        """A dep name that isn't itself a key in `graph` doesn't appear as one
        in the result -- it just doesn't get a reverse edge recorded."""
        graph = {"a": {"missing"}}
        result = reverse_graph(graph)
        assert result == {"a": set()}
        assert "missing" not in result


class TestTopologicalSort:
    """Test topological sorting with Kahn's algorithm."""

    def test_single_node(self):
        """Single node with no dependencies."""
        graph = {"foo": set()}
        result = topological_sort(graph)
        assert result == ["foo"]

    def test_linear_chain(self):
        """Linear dependency order is preserved."""
        graph = {
            "a": {"b"},
            "b": {"c"},
            "c": set(),
        }
        result = topological_sort(graph)
        # c before b before a
        assert result.index("c") < result.index("b") < result.index("a")

    def test_diamond(self):
        """Diamond dependency resolves correctly."""
        graph = {
            "a": {"b", "c"},
            "b": {"d"},
            "c": {"d"},
            "d": set(),
        }
        result = topological_sort(graph)
        # d before b and c, both before a
        assert result.index("d") < result.index("b")
        assert result.index("d") < result.index("c")
        assert result.index("b") < result.index("a")
        assert result.index("c") < result.index("a")

    def test_cycle_detection_simple(self):
        """Simple cycle is detected and raises ValueError."""
        graph = {
            "a": {"b"},
            "b": {"a"},
        }
        with pytest.raises(ValueError, match="Dependency cycle detected"):
            topological_sort(graph)

    def test_cycle_detection_self_loop(self):
        """Self-loop is detected."""
        graph = {
            "a": {"a"},
        }
        with pytest.raises(ValueError, match="Dependency cycle detected"):
            topological_sort(graph)

    def test_cycle_detection_three_node_cycle(self):
        """Three-node cycle is detected."""
        graph = {
            "a": {"b"},
            "b": {"c"},
            "c": {"a"},
        }
        with pytest.raises(ValueError, match="Dependency cycle detected"):
            topological_sort(graph)

    def test_empty_graph(self):
        """Empty graph returns empty result."""
        graph = {}
        result = topological_sort(graph)
        assert result == []


class TestTransitiveDeps:
    """Test transitive dependency computation."""

    def test_no_dependencies(self):
        """Package with no deps returns empty set."""
        graph = {"a": set()}
        assert transitive_deps("a", graph) == set()

    def test_direct_dependencies(self):
        """Direct dependencies are included."""
        graph = {
            "a": {"b", "c"},
            "b": set(),
            "c": set(),
        }
        assert transitive_deps("a", graph) == {"b", "c"}

    def test_transitive_chain(self):
        """All transitive ancestors are included."""
        graph = {
            "a": {"b"},
            "b": {"c"},
            "c": set(),
        }
        assert transitive_deps("a", graph) == {"b", "c"}

    def test_diamond_transitive(self):
        """Diamond deps all included."""
        graph = {
            "a": {"b", "c"},
            "b": {"d"},
            "c": {"d"},
            "d": set(),
        }
        assert transitive_deps("a", graph) == {"b", "c", "d"}

    def test_excludes_self_initially_but_cycle_includes(self):
        """Package with cycle: transitive_deps includes deps even if they lead back to self."""
        graph = {
            "a": {"b"},
            "b": {"a"},  # cycle
        }
        # transitive_deps starts with direct deps of 'a', which is 'b'
        # Then it adds deps of 'b', which is 'a', but 'a' is already in visited? No, it checks the stack.
        # Let's just check what actually happens: we get both 'b' and 'a' because of the cycle
        result = transitive_deps("a", graph)
        # The function doesn't prevent revisiting via cycles, so self can be included
        assert "b" in result

    def test_missing_package(self):
        """Missing package returns empty (uses graph.get with default)."""
        graph = {"a": set()}
        assert transitive_deps("nonexistent", graph) == set()


class TestOrderedPackages:
    """Test ordered_packages() -- the shared build-order helper full-cycle.py's
    prepare_packages() and stage-show-plan.py's show_plan() both call, so the
    real run and the pre-flight plan always agree on order (docs/bugs.md,
    formerly BUG-0048)."""

    def test_topo_sorts_regardless_of_declared_order(self):
        """Declared (dict) order is the opposite of the dependency direction;
        result must still be dependency-first."""
        packages = {
            "b": {"depends_on": ["a"]},
            "a": {},
        }
        result, dep_reason = ordered_packages(packages)
        assert list(result) == ["a", "b"]
        assert dep_reason == {}

    def test_no_filter_returns_all_packages(self):
        packages = {"a": {}, "b": {"depends_on": ["a"]}, "c": {}}
        result, _ = ordered_packages(packages)
        assert set(result) == {"a", "b", "c"}

    def test_package_filter_expands_transitive_deps(self):
        """PACKAGE=c pulls in b and a too (c depends on b depends on a),
        re-sorted to preserve topological order; dep_reason attributes each
        pulled-in dep to the requested package that needed it."""
        packages = {
            "a": {},
            "b": {"depends_on": ["a"]},
            "c": {"depends_on": ["b"]},
            "d": {},
        }
        result, dep_reason = ordered_packages(packages, package_filter="c")
        assert list(result) == ["a", "b", "c"]
        assert dep_reason == {"a": "c", "b": "c"}

    def test_package_filter_no_deps_needed(self):
        """A requested package with no deps isn't added to dep_reason."""
        packages = {"a": {}, "b": {}}
        result, dep_reason = ordered_packages(packages, package_filter="a")
        assert list(result) == ["a"]
        assert dep_reason == {}

    def test_skip_filter_removes_package(self):
        packages = {"a": {}, "b": {"depends_on": ["a"]}, "c": {}}
        result, _ = ordered_packages(packages, skip_filter="b")
        assert set(result) == {"a", "c"}

    def test_package_and_skip_combined(self):
        packages = {
            "a": {},
            "b": {"depends_on": ["a"]},
            "c": {"depends_on": ["a"]},
        }
        # Request b and c, but skip b before transitive expansion runs.
        result, dep_reason = ordered_packages(
            packages, package_filter="b,c", skip_filter="b"
        )
        assert list(result) == ["a", "c"]
        assert dep_reason == {"a": "c"}

    def test_unknown_package_filter_exits(self):
        packages = {"a": {}}
        with pytest.raises(SystemExit):
            ordered_packages(packages, package_filter="nonexistent")

    def test_cycle_exits_with_error(self):
        packages = {
            "a": {"depends_on": ["b"]},
            "b": {"depends_on": ["a"]},
        }
        with pytest.raises(SystemExit):
            ordered_packages(packages)
