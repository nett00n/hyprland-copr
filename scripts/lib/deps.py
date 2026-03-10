"""Dependency inference and topological sort for packages."""

from collections import deque


def infer_deps(name: str, meta: dict, all_packages: dict) -> set[str]:
    """Return set of package names that `name` depends on.

    Uses explicit `depends_on` list when present (authoritative).
    Falls back to stripping -devel suffix from build_requires entries.
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
        name: infer_deps(name, meta, all_packages)
        for name, meta in all_packages.items()
    }


def topological_sort(graph: dict[str, set[str]]) -> list[str]:
    """Kahn's algorithm: return packages in dependency-first build order.

    Packages with no deps come first. Raises ValueError on cycles.
    """
    # Count in-degree: how many dependencies each package has
    dependents: dict[str, set[str]] = {node: set() for node in graph}
    for node, deps in graph.items():
        for dep in deps:
            if dep in dependents:
                dependents[dep].add(node)
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
