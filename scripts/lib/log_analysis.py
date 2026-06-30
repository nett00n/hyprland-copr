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
_HTTP_ERROR_RE = re.compile(r"(\d{3}) Client Error: .+? for url: (\S+)")

# error: Bad file: /root/rpmbuild/SOURCES/mpvpaper-1.2.1.tar.gz: No such file or directory
_SRPM_MISSING_SOURCE_RE = re.compile(
    r"^error: Bad file: /\S+/(\S+\.tar\.(?:gz|bz2|xz)): No such file or directory"
)

# Generic error: line handler (catches miscellaneous errors)
# error: Something went wrong: details...
_GENERIC_ERROR_RE = re.compile(r"^error: (.+)$")

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

# /var/tmp/rpm-tmp.PsPh8C: line 47: cargo: command not found
_BARE_COMMAND_NOT_FOUND_RE = re.compile(
    r"^/var/tmp/rpm-tmp\.\w+: line \d+: (\S+): command not found"
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

# CMake Error at CMakeLists.txt:128 (find_package):
#   Could not find a package configuration file provided by "glslang"
_CMAKE_MISSING_PKGCONFIG_RE = re.compile(
    r"CMake Error at CMakeLists\.txt:\d+ \(find_package\):"
)

# CMake Error at /usr/share/cmake/Modules/FindPkgConfig.cmake:1093 (message):
#   The following required packages were not found:
#    - lcms2
_CMAKE_PKG_CHECK_MODULES_RE = re.compile(
    r"CMake Error at /usr/share/cmake/Modules/FindPkgConfig\.cmake:\d+ \(message\):"
)

# CMake Error at CMakeLists.txt:130 (find_package):
#   By not providing "FindQt6.cmake" in CMAKE_MODULE_PATH...
_CMAKE_MISSING_PKGCONFIG_BYNAME_RE = re.compile(r'By not providing "Find(\w+)\.cmake"')

# CMake Error at CMakeLists.txt:49 (add_library):
#   Cannot find source file:
#     cavacore.c
_CMAKE_MISSING_SOURCE_RE = re.compile(r"Cannot find source file:")

# /path/to/file.cpp:11:10: fatal error: hyprland/src/managers/HookSystemManager.hpp: No such file or directory
_COMPILER_MISSING_HEADER_RE = re.compile(
    r"^([^:]+):(\d+):\d+: fatal error: ([^:]+): No such file or directory"
)

# error: Installed (but unpackaged) file(s) found:
_UNPACKAGED_FILES_RE = re.compile(
    r"^error: Installed \(but unpackaged\) file\(s\) found:"
)

# /var/tmp/rpm-tmp.XXX: line N: cd: dirname: No such file or directory
_CD_NOT_FOUND_RE = re.compile(
    r"^/var/tmp/rpm-tmp\.\w+: line \d+: cd: ([^:]+): No such file or directory"
)

# error: Empty %files file /builddir/build/BUILD/.../debugsourcefiles.list
_EMPTY_DEBUGFILES_RE = re.compile(
    r"^error: Empty %files file /builddir/build/BUILD/[^/]+/[^/]+/debugsourcefiles\.list"
)

# error: Directory not found: /builddir/build/BUILD/.../BUILDROOT/...
# error: File not found: /builddir/build/BUILD/.../BUILDROOT/...
_FILES_NOT_FOUND_RE = re.compile(
    r"^error: (?:Directory|File) not found: /builddir/build/BUILD/[^/]+/BUILDROOT(/\S+)"
)

# error: failed to get `bitflags` as a dependency of package `cosmic-client-toolkit v0.2.0 (...)
# Caused by: [6] Could not resolve hostname (Could not resolve host: index.crates.io)
_CARGO_NETWORK_ERROR_RE = re.compile(r"^error: failed to get `([^`]+)` as a dependency")

# error: File must begin with "/": %{_userunitdir}/app-graphical.slice
_SPEC_FILE_MACRO_RE = re.compile(
    r"^error: File must begin with \"/\": (%{[^}]+}/[^'\s]+)"
)

# /path/to/file.cpp:123:45: error: 'symbol' was not declared in this scope
# /path/to/file.c:456:10: error: undefined reference to 'symbol'
_COMPILER_ERROR_RE = re.compile(r"^([^:]+):(\d+):\d+: (?:error|fatal error): (.+)$")

# /usr/bin/ld: /path/to/object.o: in function `main':
# (.text+0x123): undefined reference to `symbol'
_LINKER_UNDEFINED_REF_RE = re.compile(
    r"(?:undefined reference|undefined symbol) to ['\`]([^'`]+)['\`]"
)

# collect2: error: ld returned 1 exit status
_LINKER_RETURN_CODE_RE = re.compile(r"^collect2: error: ld returned \d+ exit status")

# error: incorrect format: unknown tag: "pkgid"
# This is a librpm format issue that can cause spec parsing to fail
_LIBRPM_FORMAT_ERROR_RE = re.compile(
    r"error: incorrect format: unknown tag: \"([^\"]+)\""
)

# Executing(%install), Executing(%package), Executing(%check) phases
# + exit code indicates failure in that phase
_RPM_PHASE_EXECUTING_RE = re.compile(
    r"^Executing\(%(\w+)\): /bin/sh -e /var/tmp/rpm-tmp\.\w+"
)

# error: Bad exit status from /var/tmp/rpm-tmp.XXX (%install)
_BAD_EXIT_STATUS_RE = re.compile(
    r"^error: Bad exit status from /var/tmp/rpm-tmp\.\w+ \(%(\w+)\)"
)

# /usr/bin/ar: unable to copy file 'libhyprland_lib.a'; reason: No space left on device
# dd: failed to open 'file': No space left on device
_NO_SPACE_LEFT_RE = re.compile(r"No space left on device")

# 1 out of 1 hunk FAILED -- saving rejects to file src/config/ConfigManager.cpp.rej
_PATCH_HUNK_FAILED_RE = re.compile(
    r"^(\d+) out of \d+ hunk(?:s)? FAILED -- saving rejects to file (.+)\.rej$"
)

# Rpm transaction errors: "- installing package ... needs 142MB more space on the / filesystem"
# May be preceded by DEBUG output or other logging
_RPM_TRANSACTION_SPACE_RE = re.compile(
    r"- installing package (\S+) needs (\d+)MB more space on (.+) filesystem"
)

# Transaction failed: Rpm transaction failed.
_TRANSACTION_FAILED_RE = re.compile(r"Transaction failed: Rpm transaction failed")


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
            continue
        m = _SRPM_MISSING_SOURCE_RE.match(line)
        if m:
            filename = m.group(1)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'source file "{filename}" not downloaded — check spectool output above for download error (network issue, URL mismatch, or authentication required)',
                    filename,
                    "http",
                )
            )
            continue
        m = _GENERIC_ERROR_RE.match(line)
        if m:
            error_msg = m.group(1).strip()
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f"SRPM error: {error_msg}",
                    error_msg,
                    "none",
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
        m = _BARE_COMMAND_NOT_FOUND_RE.match(line)
        if m:
            command = m.group(1)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'command not found: "{command}" — add to packages.yaml build_requires',
                    command,
                    "tool",
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
        m = _CMAKE_MISSING_PKGCONFIG_RE.search(line)
        if m:
            # Look for the package name in the next line
            pkg = ""
            if lineno < len(raw_lines):
                next_line = raw_lines[lineno]
                pkg_match = re.search(
                    r'Could not find a package configuration file provided by "([^"]+)"',
                    next_line,
                )
                if pkg_match:
                    pkg = pkg_match.group(1)
            if pkg:
                issues.append(
                    (
                        lineno,
                        line.strip(),
                        f'missing CMake package: "{pkg}"',
                        pkg,
                        "pkgconfig",
                    )
                )
            continue
        m = _CMAKE_MISSING_PKGCONFIG_BYNAME_RE.search(line)
        if m:
            pkg = m.group(1)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'missing CMake package: "{pkg}"',
                    pkg,
                    "pkgconfig",
                )
            )
            continue
        m = _CMAKE_PKG_CHECK_MODULES_RE.search(line)
        if m:
            # Look for package names starting with " - " in following lines
            pkgs = []
            for next_idx in range(lineno, min(lineno + 10, len(raw_lines))):
                next_line = raw_lines[next_idx]
                if next_line.strip().startswith("- "):
                    pkg = next_line.strip()[2:].strip()
                    if pkg:
                        pkgs.append(pkg)
                elif next_line.strip() and not next_line.startswith(" "):
                    # Stop at first non-indented, non-empty line
                    break
            # Report first package; others will be caught in subsequent lines
            if pkgs:
                pkg_list = ", ".join(f'"{p}"' for p in pkgs)
                issues.append(
                    (
                        lineno,
                        line.strip(),
                        f"missing pkgconfig packages: {pkg_list}",
                        pkgs[0],
                        "pkgconfig",
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
            continue
        m = _UNPACKAGED_FILES_RE.match(line)
        if m:
            issues.append(
                (
                    lineno,
                    line.strip(),
                    "installed but unpackaged files found — add missing files to files: in packages.yaml",
                    "",
                    "none",
                )
            )
            continue
        m = _CD_NOT_FOUND_RE.match(line)
        if m:
            dirname = m.group(1)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'extracted tarball directory "{dirname}" not found — package name may not match repo name, add source_name to packages.yaml (e.g., source_name: actual-repo-name)',
                    "",
                    "none",
                )
            )
            continue
        m = _EMPTY_DEBUGFILES_RE.match(line)
        if m:
            issues.append(
                (
                    lineno,
                    line.strip(),
                    "empty debugsourcefiles.list — package produces no binaries/shared libraries (likely header-only or static library), add to packages.yaml:\n        rpm:\n          no_debug_package: true",
                    "",
                    "none",
                )
            )
            continue
        m = _FILES_NOT_FOUND_RE.match(line)
        if m:
            filepath = m.group(1)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'file declared in packages.yaml but not found after build: "{filepath}" — build system does not produce this file, remove from files: in packages.yaml',
                    filepath,
                    "none",
                )
            )
            continue
        m = _CARGO_NETWORK_ERROR_RE.match(line)
        if m:
            crate = m.group(1)
            # Look for the "Caused by: failed to download from" lines to extract URL
            url = ""
            for next_line in raw_lines[lineno : min(lineno + 10, len(raw_lines))]:
                if "failed to download from" in next_line:
                    url_match = re.search(r"`([^`]+)`", next_line)
                    if url_match:
                        url = url_match.group(1)
                    break
            error_msg = f'cargo failed to download crate "{crate}" from {url} — network/DNS error during dependency resolution'
            issues.append(
                (
                    lineno,
                    line.strip(),
                    error_msg,
                    url if url else crate,
                    "none",
                )
            )
            continue
        m = _SPEC_FILE_MACRO_RE.match(line)
        if m:
            macro_path = m.group(1)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'RPM macro "{macro_path}" not expanded — add package providing macro to build_requires (e.g., systemd-rpm-macros for %{{_userunitdir}})',
                    "",
                    "none",
                )
            )
            continue
        m = _LINKER_UNDEFINED_REF_RE.search(line)
        if m:
            symbol = m.group(1)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'linker error: undefined reference to symbol "{symbol}" — missing library in build_requires or incompatible dependency version',
                    symbol,
                    "none",
                )
            )
            continue
        m = _LINKER_RETURN_CODE_RE.match(line)
        if m:
            issues.append(
                (
                    lineno,
                    line.strip(),
                    "linker error: linking failed — check previous lines for missing symbols or incompatible libraries",
                    "",
                    "none",
                )
            )
            continue
        m = _NO_SPACE_LEFT_RE.search(line)
        if m:
            issues.append(
                (
                    lineno,
                    line.strip(),
                    "build container ran out of disk space during compilation/linking — increase mock build environment size in copr settings or free disk space on build machine",
                    "",
                    "none",
                )
            )
            continue
        m = _COMPILER_ERROR_RE.match(line)
        if m:
            filepath, lineno_src, error_msg = m.group(1), m.group(2), m.group(3)
            # Classify error type
            hint = ""
            if "was not declared in this scope" in error_msg:
                hint = "undeclared identifier — missing header file or incorrect library version"
            elif "no member named" in error_msg or "has no member" in error_msg:
                hint = "struct/class has no such member — incompatible dependency version or API mismatch"
            elif "expected" in error_msg and "but got" in error_msg:
                hint = "type mismatch — check function signature or argument types (may be API change in dependency)"
            else:
                hint = error_msg.rstrip(".")
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f"compilation error (line {lineno_src}): {hint}",
                    filepath,
                    "none",
                )
            )
            continue
        m = _LIBRPM_FORMAT_ERROR_RE.search(line)
        if m:
            tag = m.group(1)
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f'librpm format error: unknown tag "{tag}" in spec file — check for invalid RPM macros or malformed spec syntax',
                    tag,
                    "none",
                )
            )
            continue
        m = _BAD_EXIT_STATUS_RE.match(line)
        if m:
            phase = m.group(1)
            phase_friendly = {
                "prep": "source preparation (%prep)",
                "build": "build (%build)",
                "install": "installation (%install)",
                "package": "packaging (%package)",
                "check": "test (%check)",
            }.get(phase, f"RPM phase ({phase})")
            # Look back for the actual error that caused the failure
            error_context = ""
            for prev_idx in range(lineno - 1, max(lineno - 50, 0), -1):
                prev_line = raw_lines[prev_idx - 1].strip()
                # Check for hunk FAILED first (most specific for prep phase)
                if "hunk FAILED" in prev_line and ".rej" in prev_line:
                    error_context = f"patch failed to apply — {prev_line}"
                    break
                if "No file to patch" in prev_line:
                    error_context = f"patch file mismatch — {prev_line}"
                    break
                if prev_line.startswith("CMake Error"):
                    error_context = prev_line
                    break
                if prev_line.startswith("error:") and not prev_line.startswith(
                    "error: Bad exit"
                ):
                    error_context = prev_line
                    break
                if any(
                    x in prev_line
                    for x in [
                        "fatal error:",
                        "FAILED",
                        "not found",
                        "No such file",
                        "undefined reference",
                    ]
                ):
                    if not prev_line.startswith(("+ ", "Executing")):
                        error_context = prev_line
                        break
            msg = f"failed during {phase_friendly}"
            if error_context:
                msg += f" — {error_context}"
            else:
                msg += " — check previous lines for the actual error"
            issues.append(
                (
                    lineno,
                    line.strip(),
                    msg,
                    phase,
                    "none",
                )
            )
            continue
        m = _PATCH_HUNK_FAILED_RE.match(line)
        if m:
            rej_file = m.group(2)
            # Look backwards to find which patch file was being applied
            patch_file = ""
            for prev_idx in range(lineno - 1, max(lineno - 20, 0), -1):
                prev_line = raw_lines[prev_idx - 1]
                if "/usr/lib/rpm/rpmuncompress" in prev_line:
                    # Extract patch filename from rpmuncompress command
                    patch_match = re.search(r"/([^/]+\.patch)(?:\s|$)", prev_line)
                    if patch_match:
                        patch_file = patch_match.group(1)
                    break
            msg = f'patch "{patch_file}" failed to apply to "{rej_file}"'
            if patch_file:
                msg += " — patch incompatible with current source; check .rej files and update patch"
            else:
                msg += " — check patch file in SOURCES directory; may be incompatible with current source"
            issues.append(
                (
                    lineno,
                    line.strip(),
                    msg,
                    patch_file or rej_file,
                    "none",
                )
            )
            continue
        m = _GENERIC_ERROR_RE.match(line)
        if m:
            error_msg = m.group(1).strip()
            issues.append(
                (
                    lineno,
                    line.strip(),
                    f"build error: {error_msg}",
                    error_msg,
                    "none",
                )
            )
            continue

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


def _analyze_mock_root_log(log_path: Path) -> list[tuple[int, str, str, str, str]]:
    """Scan the mock root installation log (-21-mock-root.log) for transaction/space errors."""
    if not log_path.exists():
        return []
    issues: list[tuple[int, str, str, str, str]] = []
    raw_lines = log_path.read_text(errors="replace").splitlines()
    transaction_reported = False

    for lineno, line in enumerate(raw_lines, start=1):
        m = _TRANSACTION_FAILED_RE.search(line)
        if m and not transaction_reported:
            space_issues = []
            for next_idx in range(lineno, min(lineno + 20, len(raw_lines) + 1)):
                if next_idx - 1 < len(raw_lines):
                    next_line = raw_lines[next_idx - 1]
                    space_m = _RPM_TRANSACTION_SPACE_RE.search(next_line)
                    if space_m:
                        pkg_name = space_m.group(1)
                        space_needed = space_m.group(2)
                        filesystem = space_m.group(3)
                        space_issues.append(
                            f"{pkg_name} needs {space_needed}MB on {filesystem}"
                        )
            if space_issues:
                msg = f"rpm transaction failed due to insufficient disk space — {'; '.join(space_issues[:3])} — increase mock root volume or free disk space on build machine"
                issues.append(
                    (
                        lineno,
                        line.strip(),
                        msg,
                        "",
                        "none",
                    )
                )
                transaction_reported = True
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
