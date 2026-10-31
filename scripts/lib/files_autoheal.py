"""Heal the files:/devel.files: lists from rpmbuild's %files errors. #COPR-0029

Two failures, never in the same build (rpmbuild stops at the first subpackage whose
%files fails):

- `File not found: …/BUILDROOT/<path>`: a declared entry the build does not produce.
  The entry covering <path> is removed -- but the spec is shared by every chroot, so a
  removal is only applied when **every supported chroot agrees** (union rule). A chroot
  that lacks the file otherwise only records a *vote*: its mock stage stays failed with
  a `pending -files:<entry>` reason, which the other chroots read back from build-report.db.
- `Installed (but unpackaged) file(s) found`: a produced file nobody declared. It is
  added, to `devel.files` when it looks like a development file, else to `files`.

See docs/features/COPR-0029-build-deps-autoheal.md.
"""

import fnmatch
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from lib import paths
from lib.log_analysis import missing_files, unpackaged_files
from lib.rpm_macros import normalize_abs_to_macro, normalize_macro_to_abs
from lib.validation import DEVEL_INDICATORS
from lib.yaml_utils import load_packages_yaml, write_yaml_file

GetStage = Callable[[str, str, str], "dict | None"]

# Macros lib/rpm_macros.py does not know (BUG-0047); expanded here, not there, so the
# abs <-> macro converter keeps its current behavior.
_SIMPLE_MACROS = {
    "%{_prefix}": "/usr",
    "%{bash_completions_dir}": "/usr/share/bash-completion/completions",
    "%{fish_completions_dir}": "/usr/share/fish/vendor_completions.d",
    "%{zsh_completions_dir}": "/usr/share/zsh/site-functions",
}
# Entries rpm resolves under BUILD, not BUILDROOT: never a buildroot path.
_SOURCE_DIRECTIVES = ("%doc", "%license")
_PENDING_RE = re.compile(r"pending (-.+?) \(needs all chroots")


@dataclass(frozen=True)
class FileEdit:
    """One edit of a file list: `op` "+" or "-", `list_name` "files" or
    "devel.files", `entry` the packages.yaml entry as written."""

    op: str
    list_name: str
    entry: str

    @property
    def key(self) -> str:
        return f"{self.list_name}:{self.entry}"

    @property
    def change(self) -> str:
        """Signed form used in stage reasons: `-files:%{_bindir}/x`."""
        return f"{self.op}{self.key}"


@dataclass
class FilePlan:
    """What a build log asks for: `edits` to apply now, `pending` removals still
    waiting for the other chroots as (edit, voting targets), including this one."""

    edits: list[FileEdit] = field(default_factory=list)
    pending: list[tuple[FileEdit, list[str]]] = field(default_factory=list)


def _lists(meta: dict) -> list[tuple[str, list]]:
    devel = meta.get("devel") or {}
    return [
        ("files", meta.get("files") or []),
        ("devel.files", devel.get("files") or []),
    ]


def entry_path(entry: str, meta: dict, name: str) -> str | None:
    """Absolute buildroot path (or glob / directory) a files: entry declares, or None
    for `%doc`/`%license` entries and entries with a macro that cannot be expanded.
    #COPR-0029"""
    parts = entry.split()
    while parts and parts[0].startswith("%") and not parts[0].startswith("%{"):
        if parts[0] in _SOURCE_DIRECTIVES:
            return None
        parts.pop(0)  # %config(noreplace), %dir, %attr(...), ...
    if len(parts) != 1:
        return None
    path = parts[0]
    macros = {
        **_SIMPLE_MACROS,
        "%{name}": name,
        "%{version}": str(meta.get("version", "")),
    }
    for macro, value in macros.items():
        path = path.replace(macro, value)
    path = normalize_macro_to_abs(path)
    return None if "%" in path else path


def _covers(declared: str, path: str) -> bool:
    """Whether the declared path/glob/directory yields `path`."""
    if declared == path or fnmatch.fnmatchcase(path, declared):
        return True
    directory = declared.rstrip("/")
    return path == directory or path.startswith(directory + "/")


def owners(path: str, meta: dict, name: str) -> list[tuple[str, str]]:
    """(list name, entry) of every declared entry that covers `path`. #COPR-0029"""
    found = []
    for list_name, entries in _lists(meta):
        for entry in entries:
            declared = entry_path(entry, meta, name)
            if declared is not None and _covers(declared, path):
                found.append((list_name, entry))
    return found


def to_entry(path: str) -> str:
    """Macro-style packages.yaml entry for an absolute path. #COPR-0029"""
    return normalize_abs_to_macro(path)


def classify(path: str) -> str:
    """ "devel.files" for development files (headers, pkgconfig, cmake, static
    archives -- the repo's DEVEL_INDICATORS), else "files". #COPR-0029"""
    entry = to_entry(path)
    if path.endswith(".a") or any(ind in entry for ind in DEVEL_INDICATORS):
        return "devel.files"
    return "files"


def pending_reason(pending: list[tuple[FileEdit, list[str]]], total: int) -> str:
    """The vote text of a stage reason (without the `autoheal: ` prefix). The counts
    are those of the least-agreed entry. #COPR-0029"""
    if not pending:
        return ""
    entries = ", ".join(f"-{edit.key}" for edit, _ in pending)
    voters = min((v for _, v in pending), key=len)
    return (
        f"pending {entries} (needs all chroots; lacking on "
        f"{len(voters)}/{total}: {', '.join(voters)})"
    )


def parse_pending(reason: str | None) -> set[str]:
    """Edit keys (`files:<entry>`) a stage reason votes to remove. #COPR-0029"""
    m = _PENDING_RE.search(reason or "")
    if not m:
        return set()
    return {key for key in re.split(r", -", m.group(1)[1:]) if key}


def _votes(pkg: str, version: str, key: str, target: str, get_stage: GetStage) -> bool:
    """Whether `target`'s latest mock row votes to remove `key` for this version."""
    row = get_stage(pkg, "mock", target)
    if not row or row.get("state") != "failed":
        return False
    if version and not str(row.get("version") or "").startswith(f"{version}-"):
        return False
    return key in parse_pending(row.get("reason"))


def plan(
    pkg: str,
    meta: dict,
    log_path: Path,
    *,
    target: str = "",
    version: str = "",
    targets: Sequence[str] = (),
    get_stage: GetStage | None = None,
) -> FilePlan:
    """Edits the mock log of `pkg` asks for, with the union rule for removals.

    `target` is the chroot that just failed, `targets` every supported chroot,
    `get_stage(pkg, stage, target)` reads the other chroots' latest rows. A removal is
    applied only when `target` is among `targets` and each of the others voted for it.
    #COPR-0029
    """
    result = FilePlan()
    removed: set[str] = set()
    for path in missing_files(log_path):
        for list_name, entry in owners(path, meta, pkg):
            edit = FileEdit("-", list_name, entry)
            if edit.key in removed or any(edit == p for p, _ in result.pending):
                continue
            if list_name == "files":
                kept = [
                    e
                    for e in meta.get("files") or []
                    if e != entry
                    and f"files:{e}" not in removed
                    and entry_path(e, meta, pkg) is not None
                ]
                if not kept:
                    continue  # never empty the main package
            voters = [
                t
                for t in targets
                if t == target
                or (get_stage and _votes(pkg, version, edit.key, t, get_stage))
            ]
            if not voters and target:
                voters = [target]
            if target in targets and len(voters) == len(targets):
                result.edits.append(edit)
                removed.add(edit.key)
            else:
                result.pending.append((edit, voters))
    for path in unpackaged_files(log_path):
        if owners(path, meta, pkg):
            continue
        # A package without a devel subpackage keeps its headers in the main one.
        list_name = classify(path) if "devel" in meta else "files"
        edit = FileEdit("+", list_name, to_entry(path))
        if edit not in result.edits:
            result.edits.append(edit)
    return result


def apply_edits(pkg: str, edits: list[FileEdit], path: Path | None = None) -> list[str]:
    """Apply `edits` to `pkg` in packages.yaml; return the signed changes that really
    changed something. Additions are appended and the list re-sorted like
    `make sort-lists` does; an emptied list stays as `[]`. #COPR-0029"""
    path = path or paths.PACKAGES_YAML
    data = load_packages_yaml(path)
    meta = data[pkg]  # KeyError for an unknown package
    changes: list[str] = []
    for edit in edits:
        if edit.list_name == "devel.files":
            holder, key = meta.setdefault("devel", {}), "files"
        else:
            holder, key = meta, "files"
        if edit.op == "-" and key not in holder:
            continue
        # An absent `files` means the default `%{_bindir}/<name>`; keep it.
        entries = holder.setdefault(
            key, [f"%{{_bindir}}/{pkg}"] if holder is meta else []
        )
        if edit.op == "+" and edit.entry not in entries:
            entries.append(edit.entry)
            entries.sort(key=lambda e: str(e).strip().lower())
            changes.append(edit.change)
        elif edit.op == "-" and edit.entry in entries:
            entries.remove(edit.entry)
            changes.append(edit.change)
    if changes:
        write_yaml_file(path, data)
    return changes
