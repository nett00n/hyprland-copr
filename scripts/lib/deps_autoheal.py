"""Heal a failed mock build by adding the build dependency it is missing. #COPR-0029

A mock build that fails on a missing pkgconfig / CMake dependency is fixed by one
`build_requires` entry (plus `depends_on` when the provider is another package of
this repo). This module turns the mock log into that edit and drives the
edit -> rebuild loop, capped at AUTOHEAL_MAX_CYCLES cycles.

Only additions, only for dependencies a provider was found for -- see
docs/features/COPR-0029-build-deps-autoheal.md.
"""

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from lib import paths
from lib.config import env_int
from lib.log_analysis import _analyze_mock_build_log, _dnf_whatprovides
from lib.yaml_utils import load_packages_yaml, write_yaml_file

DEFAULT_MAX_CYCLES = 10
# Log-analysis methods that map to a BuildRequires entry we can verify with dnf.
_HEALABLE_METHODS = ("pkgconfig", "cmake")


@dataclass(frozen=True)
class MissingDep:
    """A dependency the build asked for: `name` as the log spells it (no version
    constraint), `method` "pkgconfig" or "cmake"."""

    name: str
    method: str


@dataclass(frozen=True)
class Fix:
    """The packages.yaml edit that satisfies `dep`: `build_requires` entry, and the
    `depends_on` entry when the provider is a package of this repo."""

    dep: MissingDep
    build_requires: str
    depends_on: str | None


@dataclass
class HealResult:
    """Outcome of heal_loop(): `ok` the rebuild finally succeeded, `cycles` heal
    cycles run, `added` build_requires entries added, `reason` the stage reason
    ("" when nothing was healed)."""

    ok: bool
    cycles: int
    added: list[str]
    reason: str


def autoheal_enabled() -> bool:
    """On unless AUTOHEAL is 0/false/no (default on). #COPR-0029"""
    return os.environ.get("AUTOHEAL", "").strip().lower() not in ("0", "false", "no")


def max_cycles() -> int:
    """AUTOHEAL_MAX_CYCLES, default 10. #COPR-0029"""
    return env_int("AUTOHEAL_MAX_CYCLES", DEFAULT_MAX_CYCLES)


def missing_build_deps(log_path: Path) -> list[MissingDep]:
    """Healable missing dependencies named in a mock build log, in log order,
    without duplicates. #COPR-0029"""
    seen: dict[MissingDep, None] = {}
    for _lineno, _raw, _msg, dep, raw_method in _analyze_mock_build_log(log_path):
        method = raw_method.rstrip(",")
        if dep and method in _HEALABLE_METHODS:
            seen.setdefault(MissingDep(dep, method), None)
    return list(seen)


def _whatprovides(query: str, fedora_version: str) -> list[str]:
    """Providers of `query` in the target's own Fedora release, not the container's."""
    return _dnf_whatprovides(query, extra_args=(f"--releasever={fedora_version}",))


def resolve_dep(
    dep: MissingDep, pkg: str, all_packages: dict, fedora_version: str
) -> Fix | None:
    """Map `dep` to a packages.yaml edit for `pkg`, or None when no provider exists.

    A package of this repo that ships a devel subpackage wins (`<name>-devel` plus
    `depends_on`); otherwise dnf must confirm a Fedora provider for the
    `pkgconfig(X)` / `cmake(X)` capability. #COPR-0029
    """
    wanted = dep.name.lower()
    for name, meta in all_packages.items():
        if name.lower() == wanted and name != pkg and "devel" in (meta or {}):
            return Fix(dep, f"{name}-devel", name)
    capability = f"{dep.method}({dep.name})"
    if _whatprovides(capability, fedora_version):
        return Fix(dep, capability, None)
    return None


def apply_fixes(pkg: str, fixes: list[Fix], path: Path | None = None) -> list[str]:
    """Add each fix to `pkg` in packages.yaml; return the build_requires entries
    that were actually new. Never removes anything. #COPR-0029

    `depends_on` is only extended when the package already has one: an absent key
    means "infer from -devel names" (lib.deps.effective_deps), and creating it
    with just the new entry would drop every inferred dependency.
    """
    path = path or paths.PACKAGES_YAML
    data = load_packages_yaml(path)
    meta = data[pkg]
    requires = list(meta.get("build_requires") or [])
    added: list[str] = []
    for fix in fixes:
        if fix.build_requires not in requires:
            requires.append(fix.build_requires)
            added.append(fix.build_requires)
        depends_on = meta.get("depends_on")
        if (
            fix.depends_on
            and depends_on is not None
            and fix.depends_on not in depends_on
        ):
            depends_on.append(fix.depends_on)
    if added:
        meta["build_requires"] = sorted(requires, key=lambda r: str(r).lower())
        write_yaml_file(path, data)
    return added


def _cycles(n: int) -> str:
    return f"{n} cycle" if n == 1 else f"{n} cycles"


def heal_loop(
    pkg: str,
    *,
    log_path: Path,
    fedora_version: str,
    rebuild: Callable[[], bool],
    limit: int,
    packages_path: Path | None = None,
    load_packages: Callable[[], dict] | None = None,
) -> HealResult:
    """Heal `pkg` after a failed mock build, at most `limit` cycles. #COPR-0029

    A cycle: read the missing dependencies from `log_path`, resolve and apply
    them, call `rebuild()` (regenerate spec/SRPM and run mock again, rewriting
    `log_path`). Stops on a successful rebuild, or when a cycle can add nothing
    new -- no recognised dependency, no provider, or entries already present (the
    edit did not help, so another rebuild would only repeat the failure).
    """
    load = load_packages or (
        lambda: load_packages_yaml(packages_path or paths.PACKAGES_YAML)
    )
    all_added: list[str] = []
    cycles = 0
    ok = False
    while cycles < limit:
        deps = missing_build_deps(log_path)
        if not deps:
            break
        packages = load()
        fixes = [
            f for d in deps if (f := resolve_dep(d, pkg, packages, fedora_version))
        ]
        added = apply_fixes(pkg, fixes, path=packages_path)
        if not added:
            break
        cycles += 1
        all_added += added
        logging.info(
            "%s: autoheal cycle %d/%d: +%s", pkg, cycles, limit, ", +".join(added)
        )
        if rebuild():
            ok = True
            break
    if not cycles:
        return HealResult(False, 0, [], "")
    plus = ", ".join(f"+{e}" for e in all_added)
    reason = (
        f"autoheal: {plus} ({_cycles(cycles)})"
        if ok
        else f"autoheal: gave up after {_cycles(cycles)} ({plus})"
    )
    return HealResult(ok, cycles, all_added, reason)
