"""Heal a failed mock build: missing dependencies and file-list drift. #COPR-0029

A mock build that fails on a missing pkgconfig / CMake dependency is fixed by one
`build_requires` entry (plus `depends_on` when the provider is another package of
this repo); one that fails on its %files lists is fixed by lib.files_autoheal. This
module turns the mock log into those edits and drives the edit -> rebuild loop,
capped at AUTOHEAL_MAX_CYCLES cycles.

Dependencies are only added, and only when a provider was found; file removals need
every chroot to agree -- see docs/features/COPR-0029-build-deps-autoheal.md.
"""

import html
import logging
import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from lib import paths
from lib import files_autoheal
from lib.config import env_int
from lib.log_analysis import _analyze_mock_build_log, _dnf_whatprovides
from lib.yaml_utils import load_packages_yaml, write_yaml_file

DEFAULT_MAX_CYCLES = 10
# Log-analysis methods that map to a BuildRequires entry we can verify with dnf.
_HEALABLE_METHODS = ("pkgconfig", "cmake")
# "   - sdbus-c++>=2.0.0" in CMake's "required packages were not found" list.
_CONSTRAINT_RE = r"^\s*-\s+{name}\s*(>=|<=|=|>|<)\s*([^\s,;]+)"


@dataclass(frozen=True)
class MissingDep:
    """A dependency the build asked for: `name` as the log spells it, `method`
    "pkgconfig" or "cmake", and `constraint` the version bound the log asked for
    (">= 2.0.0"), "" when there is none."""

    name: str
    method: str
    constraint: str = ""


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
    cycles run, `changes` the signed edits made (`+pkgconfig(x)`, `-files:<entry>`),
    `reason` the stage reason ("" when nothing was healed or voted)."""

    ok: bool
    cycles: int
    changes: list[str]
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
    text = (
        html.unescape(log_path.read_text(errors="replace")) if log_path.exists() else ""
    )
    for _lineno, _raw, _msg, dep, raw_method in _analyze_mock_build_log(log_path):
        method = raw_method.rstrip(",")
        if dep and method in _HEALABLE_METHODS:
            seen.setdefault(
                MissingDep(dep, method, _constraint(text, dep, method)), None
            )
    return list(seen)


def _constraint(text: str, name: str, method: str) -> str:
    """The version bound the log asks for `name`, e.g. ">= 2.0.0"; "" if none.

    The analyzer's issue tuples carry only the stripped name, so it is read from the
    log's package list again. Only pkgconfig entries carry one: `cmake(X)` provides
    are not versioned that way.
    """
    if method != "pkgconfig":
        return ""
    m = re.search(_CONSTRAINT_RE.format(name=re.escape(name)), text, re.MULTILINE)
    return f"{m.group(1)} {m.group(2)}" if m else ""


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
    # The constraint stays in the entry and in the lookup: a release whose newest
    # provider is too old has no provider, instead of installing a useless one.
    entry = f"{dep.method}({dep.name})" + (
        f" {dep.constraint}" if dep.constraint else ""
    )
    if _whatprovides(entry, fedora_version):
        return Fix(dep, entry, None)
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
            # A constrained entry upgrades a bare `pkgconfig(X)` from an earlier heal.
            bare = fix.build_requires.split(" ", 1)[0]
            if bare != fix.build_requires and bare in requires:
                requires.remove(bare)
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
    target: str = "",
    version: str = "",
    targets: Sequence[str] = (),
    get_stage: files_autoheal.GetStage | None = None,
) -> HealResult:
    """Heal `pkg` after a failed mock build, at most `limit` cycles. #COPR-0029

    A cycle: read the missing dependencies and the file-list errors from `log_path`,
    resolve and apply them, call `rebuild()` (regenerate spec/SRPM and run mock again,
    rewriting `log_path`). Stops on a successful rebuild, or when a cycle can change
    nothing -- no recognised error, no provider, entries already present, or only
    removals still waiting for the other chroots (`target`, `version`, `targets` and
    `get_stage` are what that vote needs, see lib.files_autoheal.plan). Such a
    waiting removal is reported in the reason as `pending …`.
    """
    load = load_packages or (
        lambda: load_packages_yaml(packages_path or paths.PACKAGES_YAML)
    )
    all_changes: list[str] = []
    pending: list = []
    cycles = 0
    ok = False
    while cycles < limit:
        packages = load()
        fixes = [
            f
            for d in missing_build_deps(log_path)
            if (f := resolve_dep(d, pkg, packages, fedora_version))
        ]
        file_plan = files_autoheal.plan(
            pkg,
            packages.get(pkg) or {},
            log_path,
            target=target,
            version=version,
            targets=targets,
            get_stage=get_stage,
        )
        pending = file_plan.pending
        changes = [f"+{e}" for e in apply_fixes(pkg, fixes, path=packages_path)]
        changes += files_autoheal.apply_edits(pkg, file_plan.edits, path=packages_path)
        if not changes:
            break
        cycles += 1
        all_changes += changes
        logging.info(
            "%s: autoheal cycle %d/%d: %s", pkg, cycles, limit, ", ".join(changes)
        )
        if rebuild():
            ok = True
            break
    waiting = files_autoheal.pending_reason(pending, len(targets))
    if not cycles:
        return HealResult(False, 0, [], f"autoheal: {waiting}" if waiting else "")
    joined = ", ".join(all_changes)
    if ok:
        return HealResult(
            True, cycles, all_changes, f"autoheal: {joined} ({_cycles(cycles)})"
        )
    reason = f"autoheal: gave up after {_cycles(cycles)} ({joined})"
    if waiting:
        reason += f"; {waiting}"
    return HealResult(False, cycles, all_changes, reason)
