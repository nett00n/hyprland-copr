"""Dependency inference and topological sort for packages."""

import sys
from collections import deque

from lib.yaml_utils import filter_packages, skip_packages


def declared_deps(meta: dict) -> list[str]:
    """Return the raw `depends_on` list from package config, as declared (no inference)."""
    return list(meta.get("depends_on") or [])


def effective_deps(name: str, meta: dict, all_packages: dict) -> set[str]:
    """Return the authoritative set of package names that `name` depends on.

    Uses explicit `depends_on` list when present (authoritative).
    Falls back to stripping -devel suffix from build_requires entries.
    This is the single source of truth for the dependency DAG: build order,
    cache invalidation, force-rebuild cascade, and failure gating all use it.
    """
    pkg_by_lower = {k.lower(): k for k in all_packages}
    explicit = meta.get("depends_on")
    if explicit is not None:
        deps: set[str] = set()
        for dep in explicit:
            resolved = pkg_by_lower.get(dep.lower())
            if resolved and resolved != name:
                deps.add(resolved)
        return deps
    # Fallback: infer from build_requires -devel suffix
    deps = set()
    for dep in meta.get("build_requires") or []:
        base = dep.removesuffix("-devel").lower()
        resolved = pkg_by_lower.get(base)
        if resolved and resolved != name:
            deps.add(resolved)
    return deps


def build_dep_graph(all_packages: dict) -> dict[str, set[str]]:
    """Build {pkg_name: set[dep_pkg_name]} graph from all packages."""
    return {
        name: effective_deps(name, meta, all_packages)
        for name, meta in all_packages.items()
    }


def reverse_graph(graph: dict[str, set[str]]) -> dict[str, set[str]]:
    """Invert {pkg: deps} into {pkg: dependents}. Every key of `graph` is preserved
    as a key in the result (possibly with an empty set); a dep name that isn't
    itself a key in `graph` is not added as one."""
    dependents: dict[str, set[str]] = {node: set() for node in graph}
    for node, deps in graph.items():
        for dep in deps:
            if dep in dependents:
                dependents[dep].add(node)
    return dependents


def topological_sort(graph: dict[str, set[str]]) -> list[str]:
    """Kahn's algorithm: return packages in dependency-first build order.

    Packages with no deps come first. Raises ValueError on cycles.
    """
    # Count in-degree: how many dependencies each package has
    dependents = reverse_graph(graph)
    in_degree: dict[str, int] = {node: 0 for node in graph}
    for node, deps in graph.items():
        in_degree[node] = len(deps)

    queue: deque[str] = deque(node for node, deg in in_degree.items() if deg == 0)
    order: list[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for dependent in dependents.get(node, set()):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(order) != len(graph):
        cycle_nodes = [n for n in graph if n not in order]
        raise ValueError(f"Dependency cycle detected among: {cycle_nodes}")

    return order


def transitive_deps(name: str, graph: dict[str, set[str]]) -> set[str]:
    """Return all transitive dependencies of `name` (not including `name` itself)."""
    visited: set[str] = set()
    stack = list(graph.get(name, set()))
    while stack:
        dep = stack.pop()
        if dep in visited:
            continue
        visited.add(dep)
        stack.extend(graph.get(dep, set()) - visited)
    return visited


def ordered_packages(
    all_packages: dict, package_filter: str = "", skip_filter: str = ""
) -> tuple[dict, dict[str, str]]:
    """Topo-sort, filter, and (for a selective build) transitive-deps-expand packages.

    Single source of truth for build order: `full-cycle.py`'s `prepare_packages()`
    (the real run) and `stage-show-plan.py`'s `show_plan()` (the pre-flight preview)
    both call this, so the plan and the real run always visit packages in the same
    dependency-first order -- a cascade (e.g. a dependency's stage failing and
    forcing every downstream stage) can only be predicted correctly if the
    dependent is evaluated after its dependency (see docs/BUGS.md, formerly
    BUG-0048).

    Always topo-sorts. If `package_filter` is set, also expands to include every
    transitive dependency of each requested package (a selective build still needs
    its deps available/cached), re-sorted to preserve topological order.

    Returns (packages, dep_reason): `dep_reason` maps a dep-only package name (not
    itself requested) to the requested package name that pulled it in -- empty
    when `package_filter` is unset. Callers that don't need it (e.g. show_plan)
    can ignore the second element.
    """
    graph = build_dep_graph(all_packages)
    try:
        order = topological_sort(graph)
    except ValueError as e:
        sys.exit(f"error: {e}")

    sorted_packages = {k: all_packages[k] for k in order}
    packages = filter_packages(sorted_packages, package_filter)
    packages = skip_packages(packages, skip_filter)

    dep_reason: dict[str, str] = {}
    if package_filter:
        expanded: dict = {}
        for name in list(packages):
            for dep in transitive_deps(name, graph):
                if dep not in expanded:
                    expanded[dep] = all_packages[dep]
                    dep_reason[dep] = name
            expanded[name] = all_packages[name]
        # Re-sort the expanded set (preserve topological order)
        packages = {k: expanded[k] for k in order if k in expanded}

    return packages, dep_reason
