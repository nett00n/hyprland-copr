"""Integration tests for dependency graph and topological sorting."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from lib.deps import build_dep_graph, topological_sort, transitive_deps


class TestDependencyOrdering:
    """Test package dependency ordering and cycle detection."""

    def test_packages_loaded_in_topological_order(self):
        """Packages are sorted topologically based on depends_on."""
        packages = {
            "pkg-a": {"depends_on": []},
            "pkg-b": {"depends_on": ["pkg-a"]},
            "pkg-c": {"depends_on": ["pkg-a", "pkg-b"]},
        }

        graph = build_dep_graph(packages)
        sorted_pkgs = topological_sort(graph)

        # A must come before B and C
        a_idx = sorted_pkgs.index("pkg-a")
        b_idx = sorted_pkgs.index("pkg-b")
        c_idx = sorted_pkgs.index("pkg-c")

        assert a_idx < b_idx
        assert a_idx < c_idx
        assert b_idx < c_idx

    def test_cycle_in_packages_raises_error(self):
        """Circular dependency raises ValueError."""
        packages = {
            "pkg-a": {"depends_on": ["pkg-b"]},
            "pkg-b": {"depends_on": ["pkg-a"]},
        }

        graph = build_dep_graph(packages)
        with pytest.raises(ValueError):
            topological_sort(graph)

    def test_self_cycle_filtered_out(self):
        """Self-referential dependencies are filtered out during graph building."""
        packages = {
            "pkg-a": {"depends_on": ["pkg-a"]},
        }

        graph = build_dep_graph(packages)
        # Self-references are filtered out by effective_deps, so graph has no self-edge
        assert graph["pkg-a"] == set()
        # This means no error is raised
        sorted_pkgs = topological_sort(graph)
        assert sorted_pkgs == ["pkg-a"]

    def test_transitive_deps_resolved_through_graph(self):
        """Transitive dependencies are correctly identified."""
        packages = {
            "pkg-a": {"depends_on": []},
            "pkg-b": {"depends_on": ["pkg-a"]},
            "pkg-c": {"depends_on": ["pkg-b"]},
        }

        graph = build_dep_graph(packages)
        deps = transitive_deps("pkg-c", graph)

        assert "pkg-a" in deps
        assert "pkg-b" in deps

    def test_no_transitive_deps_when_none_exist(self):
        """Packages with no dependencies return empty set."""
        packages = {
            "pkg-a": {"depends_on": []},
        }

        graph = build_dep_graph(packages)
        deps = transitive_deps("pkg-a", graph)

        assert deps == set()

    def test_direct_deps_always_included(self):
        """Direct dependencies are always in transitive set."""
        packages = {
            "pkg-a": {"depends_on": []},
            "pkg-b": {"depends_on": ["pkg-a"]},
        }

        graph = build_dep_graph(packages)
        deps = transitive_deps("pkg-b", graph)

        assert "pkg-a" in deps

    def test_diamond_dependency_all_paths_included(self):
        """Diamond dep (A <- B,C <- D) includes all paths."""
        packages = {
            "pkg-a": {"depends_on": []},
            "pkg-b": {"depends_on": ["pkg-a"]},
            "pkg-c": {"depends_on": ["pkg-a"]},
            "pkg-d": {"depends_on": ["pkg-b", "pkg-c"]},
        }

        graph = build_dep_graph(packages)
        deps = transitive_deps("pkg-d", graph)

        assert "pkg-a" in deps
        assert "pkg-b" in deps
        assert "pkg-c" in deps

    def test_topological_sort_independent_packages_any_order(self):
        """Independent packages can appear in any order."""
        packages = {
            "pkg-x": {"depends_on": []},
            "pkg-y": {"depends_on": []},
            "pkg-z": {"depends_on": []},
        }

        graph = build_dep_graph(packages)
        sorted_pkgs = topological_sort(graph)

        # Should contain all packages
        assert set(sorted_pkgs) == {"pkg-x", "pkg-y", "pkg-z"}

    def test_complex_dag_maintains_all_deps(self):
        """Complex DAG with multiple paths maintains ordering."""
        packages = {
            "base": {"depends_on": []},
            "mid1": {"depends_on": ["base"]},
            "mid2": {"depends_on": ["base"]},
            "top": {"depends_on": ["mid1", "mid2"]},
        }

        graph = build_dep_graph(packages)
        sorted_pkgs = topological_sort(graph)

        # base < mid1, mid2 < top
        base_idx = sorted_pkgs.index("base")
        mid1_idx = sorted_pkgs.index("mid1")
        mid2_idx = sorted_pkgs.index("mid2")
        top_idx = sorted_pkgs.index("top")

        assert base_idx < mid1_idx
        assert base_idx < mid2_idx
        assert mid1_idx < top_idx
        assert mid2_idx < top_idx
