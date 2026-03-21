"""Post-build log analysis: extract actionable errors from stage logs."""

import re
import subprocess
from pathlib import Path

# meson.build:86:14: ERROR: Dependency "upower-glib" not found, tried pkgconfig
_MESON_DEP_RE = re.compile(
    r'meson\.build:\d+:\d+: ERROR: Dependency "([^"]+)" not found, tried (\S+)'
)

# meson.build:98:20: ERROR: C++ shared or static library 'sndio' not found
_MESON_LIB_RE = re.compile(
    r"meson\.build:\d+:\d+: ERROR: C(?:\+\+)? shared or static library '([^']+)' not found"
)

# No match for argument: sndio-libs-devel
_BUILDDEP_MISSING_RE = re.compile(r"^No match for argument: (\S+)")

# Problem: package pipewire-jack-audio-connection-kit-devel-1.4.10-1.fc43.x86_64 from updates conflicts with jack-audio-connection-kit-devel provided by jack-audio-connection-kit-devel-1.9.22-10.fc43.x86_64 from fedora
_PKG_CONFLICT_RE = re.compile(
    r"^Problem: package (\S+) from \S+ conflicts with (\S+) provided by (\S+) from \S+"
)

# 404 Client Error: Not Found for url: https://...
_HTTP_ERROR_RE = re.compile(r"(\d{3}) Client Error: \S+ for url: (\S+)")

# + %cmake  (unexpanded RPM macro run as shell command → "fg: no job control")
_UNEXPANDED_MACRO_RE = re.compile(r"^\+ %(\w+)")

# /var/tmp/rpm-tmp.fzFQ77: line 47: fg: no job control  (caused by unexpanded %cmake)
_FG_NO_JOB_CONTROL_RE = re.compile(
    r"^/var/tmp/rpm-tmp\.\w+: line \d+: fg: no job control"
)

# /var/tmp/rpm-tmp.fRdqHf: line 59: /usr/bin/cmake: No such file or directory
_MISSING_BINARY_RE = re.compile(
    r"^/var/tmp/rpm-tmp\.\w+: line \d+: (/\S+): No such file or directory"
)

# CMake Error: The source directory "..." does not appear to contain CMakeLists.txt.
_CMAKE_NO_CMAKELISTS_RE = re.compile(
    r'CMake Error: The source directory "([^"]+)" does not appear to contain CMakeLists\.txt'
)

# make[1]: gcc: No such file or directory
_MAKE_MISSING_TOOL_RE = re.compile(
    r"^make\[?\d*\]?:\s+(\S+): No such file or directory"
)

# cp: cannot stat '/builddir/build/BUILD/.../README.md': No such file or directory
_CP_MISSING_FILE_RE = re.compile(
    r"cp: cannot stat '/builddir/build/BUILD/[^']+/([^/']+)': No such file or directory"
)

# meson.build:78:3: ERROR: Problem encountered: iniparser library is required
_MESON_PROBLEM_RE = re.compile(
    r"meson\.build:\d+:\d+: ERROR: Problem encountered: (.+)"
)

# Looking for a fallback subproject for the dependency libcava
_MESON_WRAP_FALLBACK_RE = re.compile(
    r"Looking for a fallback subproject for the dependency (\S+)"
)

# CMake Error at CMakeLists.txt:49 (add_library):
#   Cannot find source file:
#     cavacore.c
_CMAKE_MISSING_SOURCE_RE = re.compile(r"Cannot find source file:")

# /path/to/file.cpp:11:10: fatal error: hyprland/src/managers/HookSystemManager.hpp: No such file or directory
_COMPILER_MISSING_HEADER_RE = re.compile(
    r"^([^:]+):(\d+):\d+: fatal error: ([^:]+): No such file or directory"
)


def _dnf_whatprovides(query: str) -> list[str]:
    try:
        result = subprocess.run(
            ["dnf", "repoquery", "--whatprovides", query, "--qf", "%{name}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return sorted(
            {line.strip() for line in result.stdout.splitlines() if line.strip()}
        )
    except Exception:
        return []


def _dnf_search(name: str) -> list[str]:
    """Search for packages with a name similar to `name` (strips -devel/-libs suffixes)."""
    base = re.sub(r"(-devel|-libs|-dev)$", "", name)
    try:
        result = subprocess.run(
            ["dnf", "repoquery", f"{base}*", "--qf", "%{name}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return sorted(
            {line.strip() for line in result.stdout.splitlines() if line.strip()}
        )
    except Exception:
        return []


def _suggest_providers(dep: str, method: str) -> list[str]:
    """Return package names that provide the missing dependency."""
    if method == "pkgconfig":
        return _dnf_whatprovides(f"pkgconfig({dep})")
    if method == "library":
        return _dnf_whatprovides(f"lib{dep}.so*")
    if method == "builddep":
        exact = _dnf_whatprovides(dep)
        if exact:
            return exact
        return _dnf_search(dep)
    if method == "rpm_macro":
        # Find the package that ships the macro file, e.g. %cmake → /usr/lib/rpm/macros.d/macros.cmake
        return _dnf_whatprovides(f"*/macros.{dep}")
    if method == "binary":
        # dep is the full path, e.g. /usr/bin/cmake
        return _dnf_whatprovides(dep)
    if method == "tool":
        # dep is a bare program name, e.g. gcc
        return _dnf_whatprovides(f"*/bin/{dep}")
    if method == "search":
        # free-form name hint, e.g. first word from a meson "Problem encountered" message
        return _dnf_search(dep)
    return []


def _analyze_srpm_log(log_path: Path) -> list[tuple[int, str, str, str, str]]:
    """Scan the SRPM stage log (-10-srpm.log) for source download failures."""
    if not log_path.exists():
        return []
    issues: list[tuple[int, str, str, str, str]] = []
    for lineno, line in enumerate(
        log_path.read_text(errors="replace").splitlines(), start=1
    ):
        m = _HTTP_ERROR_RE.search(line)
        if m:
            status, url = m.group(1), m.group(2)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f"HTTP {status} downloading source: {url}",
                    url,
                    "http",
                )
            )
    return issues


def _analyze_mock_build_log(log_path: Path) -> list[tuple[int, str, str, str, str]]:
    """Scan the mock build log (-21-mock-build.log) for build-time errors."""
    if not log_path.exists():
        return []
    raw_lines = log_path.read_text(errors="replace").splitlines()
    issues: list[tuple[int, str, str, str, str]] = []

    # Pass 1: line-by-line single-line patterns
    for lineno, line in enumerate(raw_lines, start=1):
        m = _MESON_DEP_RE.search(line)
        if m:
            dep, method = m.group(1), m.group(2)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'missing dependency: "{dep}" (tried {method})',
                    dep,
                    method,
                )
            )
            continue
        m = _MESON_LIB_RE.search(line)
        if m:
            dep = m.group(1)
            issues.append(
                (lineno, line.strip(), f'missing library: "{dep}"', dep, "library")
            )
            continue
        m = _UNEXPANDED_MACRO_RE.match(line)
        if m:
            macro = m.group(1)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'unexpanded RPM macro "%{macro}" executed as shell command — add to packages.yaml:\n        build_requires:\n          - cmake\n          - cmake-rpm-macros',
                    macro,
                    "rpm_macro",
                )
            )
            continue
        m = _FG_NO_JOB_CONTROL_RE.match(line)
        if m:
            issues.append(
                (
                    lineno,
                    line.strip(),
                    'unexpanded RPM macro caused "fg: no job control" — add to packages.yaml:\n        build_requires:\n          - cmake\n          - cmake-rpm-macros',
                    "cmake",
                    "rpm_macro",
                )
            )
            continue
        m = _MISSING_BINARY_RE.match(line)
        if m:
            binary = m.group(1)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'binary not found: "{binary}"',
                    binary,
                    "binary",
                )
            )
            continue
        m = _CMAKE_NO_CMAKELISTS_RE.search(line)
        if m:
            issues.append(
                (
                    lineno,
                    line.strip(),
                    'wrong build_system: "cmake" set but no CMakeLists.txt found — fix build_system in packages.yaml',
                    "",
                    "none",
                )
            )
            continue
        m = _MAKE_MISSING_TOOL_RE.match(line)
        if m:
            tool = m.group(1)
            issues.append(
                (lineno, line.strip(), f'make: tool not found: "{tool}"', tool, "tool")
            )
            continue
        m = _CP_MISSING_FILE_RE.search(line)
        if m:
            fname = m.group(1)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'source file not found: "{fname}" — remove %doc/%license entry from files in packages.yaml',
                    fname,
                    "none",
                )
            )
            continue
        m = _MESON_PROBLEM_RE.search(line)
        if m:
            problem_msg = m.group(1).strip()
            # Use the first word as a search hint (e.g. "iniparser" from "iniparser library is required")
            hint = problem_msg.split()[0] if problem_msg else ""
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f"meson problem: {problem_msg}",
                    hint,
                    "search",
                )
            )
            continue
        m = _CMAKE_MISSING_SOURCE_RE.search(line)
        if m:
            # filename is on the next non-empty line
            fname = ""
            for next_line in raw_lines[lineno:]:
                fname = next_line.strip()
                if fname:
                    break
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'CMake cannot find source file "{fname}" — likely a missing git submodule in the tarball',
                    "",
                    "none",
                )
            )
            continue
        m = _COMPILER_MISSING_HEADER_RE.match(line)
        if m:
            header = m.group(3)
            is_internal = "/src/" in header or "/internal/" in header
            msg = f'header not found: "{header}"'
            if is_internal:
                msg += " — this is a private/internal Hyprland header (plugin may be incompatible with current Hyprland version — check patch file to exclude from build)"
            issues.append(
                (
                    lineno,
                    line.strip(),
                    msg,
                    header,
                    "none",
                )
            )
            continue
        m = _MESON_WRAP_FALLBACK_RE.search(line)
        if m:
            dep = m.group(1)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'missing dependency "{dep}" — meson tried wrap fallback (disabled in RPM builds)',
                    dep,
                    "pkgconfig",
                )
            )

    # Pass 2: multi-line "Installed (but unpackaged) file(s) found:" block
    in_block = False
    block_lineno = 0
    unpackaged: list[str] = []
    for lineno, line in enumerate(raw_lines, start=1):
        stripped = line.strip()
        if "Installed (but unpackaged) file(s) found:" in stripped:
            in_block = True
            block_lineno = lineno
            unpackaged = []
            continue
        if in_block:
            if stripped.startswith("/"):
                if not stripped.startswith("/usr/lib/debug/") and not stripped.endswith(
                    ".debug"
                ):
                    unpackaged.append(stripped)
            elif stripped.startswith("Child return code") or stripped.startswith(
                "EXCEPTION:"
            ):
                in_block = False
            # else: skip interleaved non-path lines (e.g. "RPM build errors:")
    if unpackaged:
        devel_exts = {".h", ".pc"}
        main_files = [
            f for f in unpackaged if not any(f.endswith(e) for e in devel_exts)
        ]
        devel_files = [f for f in unpackaged if any(f.endswith(e) for e in devel_exts)]
        parts = []
        if main_files:
            yaml_list = "\n        ".join(f'- "{f}"' for f in main_files)
            parts.append(f"add to files: in packages.yaml:\n        {yaml_list}")
        if devel_files:
            yaml_list = "\n        ".join(f'- "{f}"' for f in devel_files)
            parts.append(f"add to devel.files: in packages.yaml:\n        {yaml_list}")
        msg = "installed but unpackaged files — " + "\n      ".join(parts)
        issues.append(
            (block_lineno, "Installed (but unpackaged) file(s) found:", msg, "", "none")
        )

    return issues


def _analyze_mock_log(log_path: Path) -> list[tuple[int, str, str, str, str]]:
    """Scan the mock orchestration log (-20-mock.log) for builddep failures."""
    if not log_path.exists():
        return []
    issues: list[tuple[int, str, str, str, str]] = []
    for lineno, line in enumerate(
        log_path.read_text(errors="replace").splitlines(), start=1
    ):
        m = _BUILDDEP_MISSING_RE.search(line)
        if m:
            pkg = m.group(1)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'build dependency not found: "{pkg}"',
                    pkg,
                    "builddep",
                )
            )
            continue
        m = _PKG_CONFLICT_RE.match(line)
        if m:
            pkg_a, capability, pkg_b = m.group(1), m.group(2), m.group(3)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'package conflict: "{pkg_a}" conflicts with "{capability}" provided by "{pkg_b}" — remove the conflicting BuildRequires from packages.yaml',
                    "",
                    "none",
                )
            )
    return issues


def _print_stage_issues(
    stage_label: str,
    pkg: str,
    log_path: Path,
    issues: list,
    first: list[bool],
) -> None:
    """Print issues for one log file. `first` is a one-element list used as a mutable flag."""
    if not issues:
        return
    if first[0]:
        print("\nPost-build analysis:")
        first[0] = False
    print(f"  [{stage_label}] {pkg}:")
    for lineno, raw_line, msg, dep, method in issues:
        print(f"    - {msg}")
        print(f"      {log_path}:{lineno}: {raw_line}")
        providers = _suggest_providers(dep, method)
        if providers:
            yaml_list = "\n        ".join(f'- "{p}"' for p in providers)
            print(f"      suggested packages:\n        {yaml_list}")


def report_srpm_failures(packages: dict, log_dir: Path) -> None:
    """Print actionable errors from SRPM stage logs."""
    first = [True]
    for pkg in packages:
        log_path = log_dir / pkg / "10-srpm.log"
        _print_stage_issues("srpm", pkg, log_path, _analyze_srpm_log(log_path), first)


def report_mock_failures(packages: dict, log_dir: Path) -> None:
    """Print actionable errors from mock stage logs."""
    first = [True]
    for pkg in packages:
        for label, filename, analyzer in [
            ("mock/builddep", "20-mock.log", _analyze_mock_log),
            ("mock/build", "21-mock-build.log", _analyze_mock_build_log),
        ]:
            log_path = log_dir / pkg / filename
            _print_stage_issues(label, pkg, log_path, analyzer(log_path), first)
