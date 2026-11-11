"""Post-build log analysis: extract actionable errors from stage logs.

#COPR-0009, #BUG-0083: each analyzer is a data table of (matcher, builder)
rules scanned top to bottom per line; the first rule that matches wins (the
old `if m: ...; continue` chain).
"""

import re
import subprocess
from collections.abc import Callable
from pathlib import Path

from lib.copr import COPR_BUILD_URL
from lib.repo_preflight import format_local_repo_remedy

# #BUG-0087: shared with pkg-log-analysis.py instead of a local copy there.
HIGHLIGHT_PREFIX = "█▓▒░"

Issue = tuple[int, str, str, str, str]
# A builder turns a regex match into zero or more (message, dep, method) triples.
_Found = list[tuple[str, str, str]]
_Builder = Callable[[re.Match, int, list[str]], _Found]
_Rule = tuple[Callable[[str], re.Match | None], _Builder]

# Looked up by more than one rule/function, so kept as named constants.
_GENERIC_ERROR_RE = re.compile(r"^error: (.+)$")
_FILES_NOT_FOUND_RE = re.compile(
    r"^error: (?:Directory|File) not found(?: by glob)?: "
    r"/builddir/build/BUILD/[^/]+/BUILDROOT(/\S+)"
)
_CMAKE_FETCHCONTENT_RETRIEVING_RE = re.compile(
    r"^--\s+(\S+) dependency not found, retrieving (\S+)"
)
_CMAKE_FETCHCONTENT_CALLSITE_RE = re.compile(
    r"^\s*(CMakeLists\.txt:\d+) \(FetchContent_MakeAvailable\)"
)
_TRANSACTION_FAILED_RE = re.compile(r"Transaction failed: Rpm transaction failed")
_FAILED_TO_RESOLVE_RE = re.compile(r"Failed to resolve the transaction:")
# - installing package X needs 142MB more space on the / filesystem
_RPM_TRANSACTION_SPACE_RE = re.compile(
    r"- installing package (\S+) needs (\d+)MB more space on (.+) filesystem"
)
# Problem: package X from _work_localrepo requires Y, but none of the providers
# can be installed
_UNSATISFIABLE_PROBLEM_RE = re.compile(
    r"Problem: package (\S+) from (\S+) requires (.+?), "
    r"but none of the providers can be installed$"
)
#   - nothing provides libdisplay-info.so.2()(64bit) needed by X from Y
_NOTHING_PROVIDES_RE = re.compile(
    r"- nothing provides (\S+) needed by (\S+) from (\S+)$"
)


def _rule(
    pattern: str,
    builder: "_Builder | str",
    dep: "int | str" = "",
    method: "int | str" = "none",
    *,
    match: bool = False,
) -> _Rule:
    """#BUG-0083: one table row. `builder` is a function, or a message template
    formatted with the match groups ({1}, {2}, ...); `dep`/`method` are literal
    strings, or an int naming the match group to take the value from."""
    rx = re.compile(pattern)

    def pick(m: re.Match, ref: "int | str") -> str:
        return m.group(ref) if isinstance(ref, int) else ref

    if callable(builder):
        return (rx.match if match else rx.search, builder)

    def fmt(m: re.Match, _lineno: int, _lines: list[str]) -> _Found:
        return [
            (builder.format(m.group(0), *m.groups()), pick(m, dep), pick(m, method))
        ]

    return (rx.match if match else rx.search, fmt)


def _scan(raw_lines: list[str], rules: list[_Rule]) -> list[Issue]:
    """#COPR-0009, #BUG-0083: run `rules` over every line, first match wins."""
    issues: list[Issue] = []
    for lineno, line in enumerate(raw_lines, start=1):
        for matcher, build in rules:
            m = matcher(line)
            if m:
                for msg, dep, method in build(m, lineno, raw_lines):
                    issues.append((lineno, line.strip(), msg, dep, method))
                break
    return issues


def _read_lines(log_path: Path) -> list[str] | None:
    """#BUG-0083: the log's lines, or None when the file does not exist."""
    if not log_path.exists():
        return None
    return log_path.read_text(errors="replace").splitlines()


def _generic_error(prefix: str) -> _Builder:
    """#BUG-0083: builder for `error: <msg>` lines -> "<prefix><msg>"."""

    def build(m: re.Match, _lineno: int, _lines: list[str]) -> _Found:
        error_msg = m.group(1).strip()
        return [(f"{prefix}{error_msg}", error_msg, "none")]

    return build


def _strip_constraint(name: str) -> str:
    """Drop a version constraint: "hyprtoolkit>=0.6.0" -> "hyprtoolkit".

    Also handles the HTML-escaped form ("&gt;=") some log viewers produce.
    """
    return re.split(r"\s*(?:[<>=!]|&[lg]t;)", name, maxsplit=1)[0].strip()


def _nvra_to_name(nvra: str) -> str:
    """Strip version-release.arch off an N-V-R.A string, e.g.
    "aquamarine-0.14.0-10.fc43.x86_64" -> "aquamarine"."""
    return nvra.rsplit("-", 2)[0] if nvra.count("-") >= 2 else nvra


def _dnf_whatprovides(query: str, extra_args: tuple[str, ...] = ()) -> list[str]:
    """Names of packages providing `query`. #COPR-0029

    `extra_args` go straight to dnf (e.g. `--releasever=45` to query another
    release than the container's). `--qf` ends in an explicit `\\n`: dnf5 does not
    add one, so several matches would otherwise come back joined on one line.
    """
    try:
        result = subprocess.run(
            [
                "dnf",
                "repoquery",
                *extra_args,
                "--whatprovides",
                query,
                "--qf",
                "%{name}\\n",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
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
            ["dnf", "repoquery", f"{base}*", "--qf", "%{name}\\n"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return sorted(
            {line.strip() for line in result.stdout.splitlines() if line.strip()}
        )
    except Exception:
        return []


def suggest_providers(dep: str, method: str) -> list[str]:
    """#COPR-0009, #BUG-0087: return package names that provide the missing dependency."""
    if method == "pkgconfig":
        return _dnf_whatprovides(f"pkgconfig({dep})")
    if method == "cmake":
        # #COPR-0029: CMake config packages are provided as cmake(X), usually
        # with X's exact case; some -devel packages only provide the lowercase.
        return _dnf_whatprovides(f"cmake({dep})") or _dnf_whatprovides(
            f"cmake({dep.lower()})"
        )
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


def _cmake_find_package(m: re.Match, lineno: int, raw_lines: list[str]) -> _Found:
    """#BUG-0083: package name is on the line after `find_package):`."""
    pkg = ""
    if lineno < len(raw_lines):
        pkg_match = re.search(
            r'Could not find a package configuration file provided by "([^"]+)"',
            raw_lines[lineno],
        )
        if pkg_match:
            pkg = pkg_match.group(1)
    return [(f'missing CMake package: "{pkg}"', pkg, "cmake")] if pkg else []


def _cmake_pkg_check_modules(m: re.Match, lineno: int, raw_lines: list[str]) -> _Found:
    """#BUG-0083, #COPR-0029: one issue per ` - pkg` line that follows, version
    constraint stripped ("hyprtoolkit>=0.6.0" -> "hyprtoolkit") so each can be
    resolved and healed on its own."""
    pkgs = []
    for next_line in raw_lines[lineno : min(lineno + 10, len(raw_lines))]:
        if next_line.strip().startswith("- "):
            pkg = next_line.strip()[2:].strip()
            if pkg:
                pkgs.append(pkg)
        elif next_line.strip() and not next_line.startswith(" "):
            break  # first non-indented, non-empty line ends the list
    return [
        (f'missing pkgconfig package: "{pkg}"', pkg, "pkgconfig")
        for pkg in dict.fromkeys(_strip_constraint(p) for p in pkgs)
    ]


def _cmake_fetchcontent(m: re.Match, lineno: int, raw_lines: list[str]) -> _Found:
    """#BUG-0083: CMake fell back to FetchContent (no git/network in mock)."""
    dep = re.sub(r"-populate$", "", m.group(1))
    version = ""
    for prev_idx in range(lineno - 1, max(lineno - 10, 0), -1):
        prev_m = _CMAKE_FETCHCONTENT_RETRIEVING_RE.match(raw_lines[prev_idx - 1])
        if prev_m:
            version = prev_m.group(2)
            break
    callsite = ""
    for next_idx in range(lineno, min(lineno + 15, len(raw_lines))):
        next_m = _CMAKE_FETCHCONTENT_CALLSITE_RE.match(raw_lines[next_idx])
        if next_m:
            callsite = next_m.group(1)
            break
    msg = f'CMake fell back to FetchContent for "{dep}"'
    if version:
        msg += f" (wants {version})"
    if callsite:
        msg += f" at {callsite}"
    msg += (
        " — git/network are unavailable in mock. Add a system package"
        f' providing "{dep}" to build_requires in packages.yaml; if it is'
        " already listed, the buildroot version does not satisfy"
        " upstream's version pin (patch the pin or provide a matching"
        " version)."
    )
    return [(msg, dep, "builddep")]


def _meson_problem(m: re.Match, lineno: int, raw_lines: list[str]) -> _Found:
    """#BUG-0083: first word of the problem text is the search hint."""
    problem_msg = m.group(1).strip()
    hint = problem_msg.split()[0] if problem_msg else ""
    return [(f"meson problem: {problem_msg}", hint, "search")]


def _cmake_missing_source(m: re.Match, lineno: int, raw_lines: list[str]) -> _Found:
    """#BUG-0083: filename is on the next non-empty line."""
    fname = ""
    for next_line in raw_lines[lineno:]:
        fname = next_line.strip()
        if fname:
            break
    return [
        (
            f'CMake cannot find source file "{fname}" — likely a missing git submodule in the tarball',
            "",
            "none",
        )
    ]


def _missing_header(m: re.Match, lineno: int, raw_lines: list[str]) -> _Found:
    """#BUG-0083: flag private Hyprland headers (plugin/version mismatch)."""
    header = m.group(3)
    msg = f'header not found: "{header}"'
    if "/src/" in header or "/internal/" in header:
        msg += " — this is a private/internal Hyprland header (plugin may be incompatible with current Hyprland version — check patch file to exclude from build)"
    return [(msg, header, "none")]


def _cargo_network(m: re.Match, lineno: int, raw_lines: list[str]) -> _Found:
    """#BUG-0083: pull the registry URL from the following `Caused by:` lines."""
    crate = m.group(1)
    url = ""
    for next_line in raw_lines[lineno : min(lineno + 10, len(raw_lines))]:
        if "failed to download from" in next_line:
            url_match = re.search(r"`([^`]+)`", next_line)
            if url_match:
                url = url_match.group(1)
            break
    msg = f'cargo failed to download crate "{crate}" from {url} — network/DNS error during dependency resolution'
    return [(msg, url if url else crate, "none")]


def _compiler_error(m: re.Match, lineno: int, raw_lines: list[str]) -> _Found:
    """#BUG-0083: classify a `file:line:col: error: msg` compiler diagnostic."""
    filepath, lineno_src, error_msg = m.group(1), m.group(2), m.group(3)
    if "was not declared in this scope" in error_msg:
        hint = (
            "undeclared identifier — missing header file or incorrect library version"
        )
    elif "no member named" in error_msg or "has no member" in error_msg:
        hint = "struct/class has no such member — incompatible dependency version or API mismatch"
    elif "expected" in error_msg and "but got" in error_msg:
        hint = "type mismatch — check function signature or argument types (may be API change in dependency)"
    else:
        hint = error_msg.rstrip(".")
    return [(f"compilation error (line {lineno_src}): {hint}", filepath, "none")]


_PHASE_FRIENDLY = {
    "prep": "source preparation (%prep)",
    "build": "build (%build)",
    "install": "installation (%install)",
    "package": "packaging (%package)",
    "check": "test (%check)",
}


def _bad_exit_context(lineno: int, raw_lines: list[str]) -> str:
    """#BUG-0083: look back up to 50 lines for the error behind a bad exit."""
    for prev_idx in range(lineno - 1, max(lineno - 50, 0), -1):
        prev_line = raw_lines[prev_idx - 1].strip()
        # hunk FAILED first (most specific for the prep phase)
        if "hunk FAILED" in prev_line and ".rej" in prev_line:
            return f"patch failed to apply — {prev_line}"
        if "No file to patch" in prev_line:
            return f"patch file mismatch — {prev_line}"
        if prev_line.startswith("CMake Error"):
            return prev_line
        if prev_line.startswith("error:") and not prev_line.startswith(
            "error: Bad exit"
        ):
            return prev_line
        if any(
            x in prev_line
            for x in [
                "fatal error:",
                ": error:",  # compiler diagnostics: path:line:col: error: msg
                "FAILED",
                "not found",
                "No such file",
                "undefined reference",
            ]
        ) and not prev_line.startswith(("+ ", "Executing")):
            return prev_line
    return ""


def _bad_exit_status(m: re.Match, lineno: int, raw_lines: list[str]) -> _Found:
    """#BUG-0083: `Bad exit status from ... (%phase)` plus the cause above it."""
    phase = m.group(1)
    phase_friendly = _PHASE_FRIENDLY.get(phase, f"RPM phase ({phase})")
    error_context = _bad_exit_context(lineno, raw_lines)
    msg = f"failed during {phase_friendly}"
    if error_context:
        msg += f" — {error_context}"
    else:
        msg += " — check previous lines for the actual error"
    return [(msg, phase, "none")]


def _patch_hunk_failed(m: re.Match, lineno: int, raw_lines: list[str]) -> _Found:
    """#BUG-0083: name the patch file by looking back for the rpmuncompress call."""
    rej_file = m.group(2)
    patch_file = ""
    for prev_idx in range(lineno - 1, max(lineno - 20, 0), -1):
        prev_line = raw_lines[prev_idx - 1]
        if "/usr/lib/rpm/rpmuncompress" in prev_line:
            patch_match = re.search(r"/([^/]+\.patch)(?:\s|$)", prev_line)
            if patch_match:
                patch_file = patch_match.group(1)
            break
    msg = f'patch "{patch_file}" failed to apply to "{rej_file}"'
    if patch_file:
        msg += " — patch incompatible with current source; check .rej files and update patch"
    else:
        msg += " — check patch file in SOURCES directory; may be incompatible with current source"
    return [(msg, patch_file or rej_file, "none")]


_ADD_CMAKE_RPM_MACROS = (
    "add to packages.yaml:\n        build_requires:\n          - cmake\n"
    "          - cmake-rpm-macros"
)
_RPM_TMP = r"^/var/tmp/rpm-tmp\.\w+: line \d+: "

# #COPR-0009: -10-srpm.log -- source download failures.
_SRPM_RULES: list[_Rule] = [
    # 404 Client Error: Not Found for url: https://...
    _rule(
        r"(\d{3}) Client Error: .+? for url: (\S+)",
        "HTTP {1} downloading source: {2}",
        2,
        "http",
    ),
    # error: Bad file: /root/rpmbuild/SOURCES/mpvpaper-1.2.1.tar.gz: No such file...
    _rule(
        r"^error: Bad file: /\S+/(\S+\.tar\.(?:gz|bz2|xz)): No such file or directory",
        'source file "{1}" not downloaded — check spectool output above for download error (network issue, URL mismatch, or authentication required)',
        1,
        "http",
        match=True,
    ),
    _rule(_GENERIC_ERROR_RE.pattern, _generic_error("SRPM error: "), match=True),
]

# #COPR-0009: -20-mock.log -- builddep failures.
_MOCK_RULES: list[_Rule] = [
    # No match for argument: sndio-libs-devel
    _rule(
        r"^No match for argument: (\S+)",
        'build dependency not found: "{1}"',
        1,
        "builddep",
    ),
    # Problem: package X from updates conflicts with Y provided by Z from fedora
    _rule(
        r"^Problem: package (\S+) from \S+ conflicts with (\S+) provided by (\S+) from \S+",
        'package conflict: "{1}" conflicts with "{2}" provided by "{3}" — remove the conflicting BuildRequires from packages.yaml',
        match=True,
    ),
]

# #COPR-0009: -21-mock-build.log -- build-time errors. Order is precedence.
_MOCK_BUILD_RULES: list[_Rule] = [
    # meson.build:86:14: ERROR: Dependency "upower-glib" not found, tried pkgconfig
    _rule(
        r'meson\.build:\d+:\d+: ERROR: Dependency "([^"]+)" not found, tried (\S+)',
        'missing dependency: "{1}" (tried {2})',
        1,
        2,
    ),
    # meson.build:98:20: ERROR: C++ shared or static library 'sndio' not found
    _rule(
        r"meson\.build:\d+:\d+: ERROR: C(?:\+\+)? shared or static library '([^']+)' not found",
        'missing library: "{1}"',
        1,
        "library",
    ),
    # + %cmake  (unexpanded RPM macro run as shell command)
    _rule(
        r"^\+ %(\w+)",
        'unexpanded RPM macro "%{1}" executed as shell command — '
        + _ADD_CMAKE_RPM_MACROS,
        1,
        "rpm_macro",
        match=True,
    ),
    # /var/tmp/rpm-tmp.fzFQ77: line 47: fg: no job control  (unexpanded %cmake)
    _rule(
        _RPM_TMP + r"fg: no job control",
        'unexpanded RPM macro caused "fg: no job control" — ' + _ADD_CMAKE_RPM_MACROS,
        "cmake",
        "rpm_macro",
        match=True,
    ),
    # /var/tmp/rpm-tmp.fRdqHf: line 59: /usr/bin/cmake: No such file or directory
    _rule(
        _RPM_TMP + r"(/\S+): No such file or directory",
        'binary not found: "{1}"',
        1,
        "binary",
        match=True,
    ),
    # /var/tmp/rpm-tmp.PsPh8C: line 47: cargo: command not found
    _rule(
        _RPM_TMP + r"(\S+): command not found",
        'command not found: "{1}" — add to packages.yaml build_requires',
        1,
        "tool",
        match=True,
    ),
    # CMake Error: The source directory "..." does not appear to contain CMakeLists.txt.
    _rule(
        r'CMake Error: The source directory "([^"]+)" does not appear to contain CMakeLists\.txt',
        'wrong build_system: "cmake" set but no CMakeLists.txt found — fix build_system in packages.yaml',
    ),
    # ERROR: Neither source directory '.' nor build directory '...' contain a build file meson.build.
    _rule(
        r"ERROR: Neither source directory '([^']*)' nor build directory '([^']*)' contain a build file meson\.build",
        "meson.build not found in extracted source tree — source_dir in packages.yaml does not match the archive's top-level directory, or the tarball/version/fork is wrong (e.g. source predates meson support)",
    ),
    # CMake Error at CMakeLists.txt:128 (find_package):
    #   Could not find a package configuration file provided by "glslang"
    _rule(
        r"CMake Error at CMakeLists\.txt:\d+ \(find_package\):",
        _cmake_find_package,
    ),
    #   By not providing "FindQt6.cmake" in CMAKE_MODULE_PATH...
    _rule(
        r'By not providing "Find(\w+)\.cmake"',
        'missing CMake package: "{1}"',
        1,
        "cmake",
    ),
    # CMake Error at /usr/share/cmake/Modules/FindPkgConfig.cmake:1093 (message):
    #   The following required packages were not found:
    #    - lcms2
    _rule(
        r"CMake Error at /usr/share/cmake/Modules/FindPkgConfig\.cmake:\d+ \(message\):",
        _cmake_pkg_check_modules,
    ),
    #   error: could not find git for clone of glaze-populate
    _rule(r"error: could not find git for clone of (\S+)", _cmake_fetchcontent),
    # make[1]: gcc: No such file or directory
    _rule(
        r"^make\[?\d*\]?:\s+(\S+): No such file or directory",
        'make: tool not found: "{1}"',
        1,
        "tool",
        match=True,
    ),
    # gmake[2]: *** No rule to make target 'x', needed by 'y'.  Stop.
    _rule(
        r"^\S*make\[?\d*\]?: \*\*\* No rule to make target '([^']+)', needed by '([^']+)'",
        'no rule to make target "{1}", needed by "{2}" — expected'
        " source/generated file is missing; check earlier in the log for a"
        " failed code-generation step (e.g. qdbusxml2cpp/moc) or a file"
        " missing from the source tarball",
        1,
        match=True,
    ),
    # cp: cannot stat '/builddir/build/BUILD/.../README.md': No such file or directory
    _rule(
        r"cp: cannot stat '/builddir/build/BUILD/[^']+/([^/']+)': No such file or directory",
        'source file not found: "{1}" — remove %doc/%license entry from files in packages.yaml',
        1,
    ),
    # meson.build:78:3: ERROR: Problem encountered: iniparser library is required
    _rule(r"meson\.build:\d+:\d+: ERROR: Problem encountered: (.+)", _meson_problem),
    # CMake Error at CMakeLists.txt:49 (add_library):  Cannot find source file:
    _rule(r"Cannot find source file:", _cmake_missing_source),
    # /path/file.cpp:11:10: fatal error: x.hpp: No such file or directory
    _rule(
        r"^([^:]+):(\d+):\d+: fatal error: ([^:]+): No such file or directory",
        _missing_header,
        match=True,
    ),
    # Looking for a fallback subproject for the dependency libcava
    _rule(
        r"Looking for a fallback subproject for the dependency (\S+)",
        'missing dependency "{1}" — meson tried wrap fallback (disabled in RPM builds)',
        1,
        "pkgconfig",
    ),
    # error: Installed (but unpackaged) file(s) found:  (details: pass 2)
    _rule(
        r"^error: Installed \(but unpackaged\) file\(s\) found:",
        "installed but unpackaged files found — add missing files to files: in packages.yaml",
        match=True,
    ),
    # /var/tmp/rpm-tmp.XXX: line N: cd: dirname: No such file or directory
    _rule(
        _RPM_TMP + r"cd: ([^:]+): No such file or directory",
        'extracted tarball directory "{1}" not found — package name may not match repo name, add source_name to packages.yaml (e.g., source_name: actual-repo-name)',
        match=True,
    ),
    # error: Empty %files file /builddir/build/BUILD/.../debugsourcefiles.list
    _rule(
        r"^error: Empty %files file /builddir/build/BUILD/[^/]+/[^/]+/debugsourcefiles\.list",
        "empty debugsourcefiles.list — package produces no binaries/shared libraries (likely header-only or static library), add to packages.yaml:\n        rpm:\n          no_debug_package: true",
        match=True,
    ),
    # error: File not found: /builddir/build/BUILD/.../BUILDROOT/...
    _rule(
        _FILES_NOT_FOUND_RE.pattern,
        'file declared in packages.yaml but not found after build: "{1}" — build system does not produce this file, remove from files: in packages.yaml',
        1,
        match=True,
    ),
    # error: failed to get `bitflags` as a dependency of package `...`
    _rule(
        r"^error: failed to get `([^`]+)` as a dependency",
        _cargo_network,
        match=True,
    ),
    # error: File must begin with "/": %{_userunitdir}/app-graphical.slice
    _rule(
        r"^error: File must begin with \"/\": (%{[^}]+}/[^'\s]+)",
        'RPM macro "{1}" not expanded — add package providing macro to build_requires (e.g., systemd-rpm-macros for %{{_userunitdir}})',
        match=True,
    ),
    # (.text+0x123): undefined reference to `symbol'
    _rule(
        r"(?:undefined reference|undefined symbol) to ['\`]([^'`]+)['\`]",
        'linker error: undefined reference to symbol "{1}" — missing library in build_requires or incompatible dependency version',
        1,
    ),
    # collect2: error: ld returned 1 exit status
    _rule(
        r"^collect2: error: ld returned \d+ exit status",
        "linker error: linking failed — check previous lines for missing symbols or incompatible libraries",
        match=True,
    ),
    # dd: failed to open 'file': No space left on device
    _rule(
        r"No space left on device",
        "build container ran out of disk space during compilation/linking — increase mock build environment size in copr settings or free disk space on build machine",
    ),
    # /path/file.cpp:123:45: error: 'symbol' was not declared in this scope
    _rule(
        r"^([^:]+):(\d+):\d+: (?:error|fatal error): (.+)$",
        _compiler_error,
        match=True,
    ),
    # error: incorrect format: unknown tag: "pkgid"
    _rule(
        r"error: incorrect format: unknown tag: \"([^\"]+)\"",
        'librpm format error: unknown tag "{1}" in spec file — check for invalid RPM macros or malformed spec syntax',
        1,
    ),
    # ValueError: No License-File (PEP 639) in upstream metadata found.
    _rule(
        r"^ValueError: No License-File \(PEP 639\) in upstream metadata found",
        "%pyproject_save_files -l could not auto-detect a license file"
        " (upstream metadata has no PEP 639 License-File) — regenerate"
        ' the spec with gen-spec.py, which now passes "-L" instead of'
        ' "-l" (the %license entry in files: still packages it manually)',
        match=True,
    ),
    # error: Bad exit status from /var/tmp/rpm-tmp.XXX (%install)
    _rule(
        r"^error: Bad exit status from /var/tmp/rpm-tmp\.\w+ \(%(\w+)\)",
        _bad_exit_status,
        match=True,
    ),
    # 1 out of 1 hunk FAILED -- saving rejects to file src/x.cpp.rej
    _rule(
        r"^(\d+) out of \d+ hunk(?:s)? FAILED -- saving rejects to file (.+)\.rej$",
        _patch_hunk_failed,
        match=True,
    ),
    # catch-all for any other `error: ...` line
    _rule(_GENERIC_ERROR_RE.pattern, _generic_error("build error: "), match=True),
]

# #COPR-0009: -30-copr.log -- written by `copr-cli build` when
# SYNCHRONOUS_COPR_BUILD=true watches a build to a failed terminal state. Has
# no leading "error:", so _GENERIC_ERROR_RE never matched it.
_COPR_RULES: list[_Rule] = [
    _rule(
        r"^Build error: Build\(s\) (\d+) failed",
        lambda m, _n, _l: [
            (
                f"Copr build {m.group(1)} failed — see "
                f"{COPR_BUILD_URL.format(m.group(1))} "
                "and 31-copr-<chroot>.log (if fetched) for the per-chroot builder output",
                m.group(1),
                "none",
            )
        ],
        match=True,
    ),
]


def _analyze_rules(log_path: Path, rules: list[_Rule]) -> list[Issue]:
    """#BUG-0083: scan `log_path` with `rules` ([] when the log is absent)."""
    raw_lines = _read_lines(log_path)
    return _scan(raw_lines, rules) if raw_lines is not None else []


def analyze_srpm_log(log_path: Path) -> list[Issue]:
    """#COPR-0009, #BUG-0083: scan the SRPM stage log (-10-srpm.log) for source download failures."""
    return _analyze_rules(log_path, _SRPM_RULES)


def analyze_mock_log(log_path: Path) -> list[Issue]:
    """#COPR-0009, #BUG-0083: scan the mock orchestration log (-20-mock.log) for builddep failures."""
    return _analyze_rules(log_path, _MOCK_RULES)


def analyze_mock_build_log(log_path: Path) -> list[Issue]:
    """#COPR-0009, #BUG-0083: scan the mock build log (-21-mock-build.log) for build-time errors."""
    raw_lines = _read_lines(log_path)
    if raw_lines is None:
        return []
    # Pass 1: line-by-line single-line patterns
    issues = _scan(raw_lines, _MOCK_BUILD_RULES)

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


def missing_files(log_path: Path) -> list[str]:
    """Absolute paths rpmbuild reports as declared in %files but not installed
    (`File not found`, `File not found by glob`, `Directory not found`), BUILDROOT
    prefix stripped, in log order, without duplicates. #COPR-0029"""
    if not log_path.exists():
        return []
    found = (
        _FILES_NOT_FOUND_RE.match(line)
        for line in log_path.read_text(errors="replace").splitlines()
    )
    return list(dict.fromkeys(m.group(1) for m in found if m))


def unpackaged_files(log_path: Path) -> list[str]:
    """Absolute paths of every file in rpmbuild's `Installed (but unpackaged)
    file(s) found:` block(s), debug files skipped, without duplicates. #COPR-0029"""
    if not log_path.exists():
        return []
    files: dict[str, None] = {}
    in_block = False
    for line in log_path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if "Installed (but unpackaged) file(s) found:" in stripped:
            in_block = True
        elif in_block and stripped.startswith("/"):
            if not stripped.startswith("/usr/lib/debug/") and not stripped.endswith(
                ".debug"
            ):
                files.setdefault(stripped)
        elif stripped.startswith(("Child return code", "EXCEPTION:")):
            in_block = False
    return list(files)


def analyze_mock_root_log(log_path: Path) -> list[tuple[int, str, str, str, str]]:
    """#COPR-0009, #BUG-0087: scan the mock root installation log (-21-mock-root.log) for transaction/space errors."""
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

        m = _FAILED_TO_RESOLVE_RE.search(line)
        if m:
            for next_idx in range(lineno, min(lineno + 20, len(raw_lines) + 1)):
                next_line = raw_lines[next_idx - 1]
                problem_m = _UNSATISFIABLE_PROBLEM_RE.search(next_line)
                if not problem_m:
                    continue
                pkg, repo, requirement = problem_m.group(1, 2, 3)
                providers = []
                stale_local_pkgs: list[str] = []
                for provides_idx in range(
                    next_idx, min(next_idx + 10, len(raw_lines) + 1)
                ):
                    provides_line = raw_lines[provides_idx - 1]
                    provides_m = _NOTHING_PROVIDES_RE.search(provides_line)
                    if provides_m:
                        capability, needed_by, needed_by_repo = provides_m.group(
                            1, 2, 3
                        )
                        providers.append(
                            f"nothing provides {capability} needed by {needed_by} "
                            f"from {needed_by_repo}"
                        )
                        if "local" in needed_by_repo.lower():
                            name = _nvra_to_name(needed_by)
                            if name not in stale_local_pkgs:
                                stale_local_pkgs.append(name)
                msg = (
                    f"unsatisfiable buildroot dependency: {pkg} from {repo} requires "
                    f"{requirement}, but none of the providers can be installed"
                )
                if providers:
                    msg += " — " + "; ".join(providers)
                if "local" in repo.lower() or stale_local_pkgs:
                    names = stale_local_pkgs or [_nvra_to_name(pkg)]
                    # Shared with lib/repo_preflight.py's pre-build check so a
                    # build-time failure and a log-analysis-time diagnosis of the
                    # same underlying problem never drift into different wording.
                    msg += " — " + format_local_repo_remedy(names, "<ver>")
                issues.append((lineno, line.strip(), msg, "", "none"))
                break
    return issues


def analyze_copr_log(log_path: Path) -> list[Issue]:
    """#COPR-0009, #BUG-0083: scan the Copr submission log (-30-copr.log) for build failures.

    In async mode (default) the stage log just records submission; failure
    is only known once polled later, so this typically finds nothing. In
    synchronous mode (SYNCHRONOUS_COPR_BUILD=true) copr-cli watches the
    build to completion and prints "Build error: Build(s) N failed." on
    failure -- this is the whole visible failure signal without also having
    the per-chroot builder logs (see analyze_copr_chroot_logs).
    """
    return _analyze_rules(log_path, _COPR_RULES)


def analyze_copr_chroot_summary(
    log_path: Path,
) -> list[tuple[int, str, str, str, str]]:
    """#COPR-0009, #BUG-0087: scan the per-chroot summary (-30-copr-chroots.log) for a chroot mismatch.

    Written by lib.copr.fetch_failed_chroot_logs: one line per chroot,
    "<name> <state> <result_url>". Copr builds every chroot in the project
    (e.g. fedora-43/44/rawhide x86_64/aarch64) while local mock only builds
    one FEDORA_VERSION target -- so a failure that's specific to some chroots
    can never reproduce locally. Surfacing that split is the single most
    actionable fact, ahead of the per-chroot compiler errors.
    """
    if not log_path.exists():
        return []
    failed: list[str] = []
    succeeded: list[str] = []
    for line in log_path.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, state = parts[0], parts[1]
        if state == "failed":
            failed.append(name)
        elif state == "succeeded":
            succeeded.append(name)
    if not failed or not succeeded:
        return []
    msg = (
        f"failed on {', '.join(failed)} only ({len(succeeded)} succeeded: "
        f"{', '.join(succeeded)}) — release/toolchain-specific breakage, "
        "consider an os_overrides skip in packages.yaml"
    )
    return [
        (
            1,
            f"chroots: {len(failed)} failed, {len(succeeded)} succeeded",
            msg,
            "",
            "none",
        )
    ]


def analyze_copr_chroot_logs(
    pkg_log_dir: Path,
) -> dict[str, list[tuple[int, str, str, str, str]]]:
    """#COPR-0009, #BUG-0087: scan downloaded per-chroot Copr builder logs (31-copr-<chroot>.log).

    These are full mock build logs in the same format as -21-mock-build.log
    (fetched by lib.copr.fetch_failed_chroot_logs after a Copr build fails),
    so this reuses analyze_mock_build_log verbatim instead of duplicating
    its patterns.

    Returns {chroot_name: issues} for each 31-copr-*.log with issues found.
    """
    if not pkg_log_dir.exists():
        return {}
    results: dict[str, list[tuple[int, str, str, str, str]]] = {}
    for log_path in sorted(pkg_log_dir.glob("31-copr-*.log")):
        chroot_name = log_path.stem.removeprefix("31-copr-")
        issues = analyze_mock_build_log(log_path)
        if issues:
            results[chroot_name] = issues
    return results


def _print_stage_issues(
    stage_label: str,
    pkg: str,
    log_path: Path,
    issues: list,
    first: list[bool],
    version: str = "",
) -> None:
    """Print issues for one log file. `first` is a one-element list used as a mutable flag."""
    if not issues:
        return
    if first[0]:
        print("\nPost-build analysis:")
        first[0] = False
    pkg_label = f"{pkg} {version}" if version else pkg
    print(f"  [{stage_label}] {pkg_label}:")
    for lineno, raw_line, msg, dep, method in issues:
        print(f"    - {msg}")
        print(f"      {log_path}:{lineno}: {raw_line}")
        providers = suggest_providers(dep, method)
        if providers:
            yaml_list = "\n        ".join(f'- "{p}"' for p in providers)
            print(f"      suggested packages:\n        {yaml_list}")


def report_srpm_failures(
    packages: dict, log_dir: Path, versions: dict[str, str] | None = None
) -> None:
    """Print actionable errors from SRPM stage logs."""
    versions = versions or {}
    first = [True]
    for pkg in packages:
        log_path = log_dir / pkg / "10-srpm.log"
        _print_stage_issues(
            "srpm",
            pkg,
            log_path,
            analyze_srpm_log(log_path),
            first,
            versions.get(pkg, ""),
        )


def report_mock_failures(
    packages: dict, log_dir: Path, versions: dict[str, str] | None = None
) -> None:
    """Print actionable errors from mock stage logs."""
    versions = versions or {}
    first = [True]
    for pkg in packages:
        for label, filename, analyzer in [
            ("mock/builddep", "20-mock.log", analyze_mock_log),
            ("mock/build", "21-mock-build.log", analyze_mock_build_log),
        ]:
            log_path = log_dir / pkg / filename
            _print_stage_issues(
                label, pkg, log_path, analyzer(log_path), first, versions.get(pkg, "")
            )


def report_copr_failures(
    packages: dict, log_dir: Path, versions: dict[str, str] | None = None
) -> None:
    """Print actionable errors from Copr stage logs.

    Order matters: the chroot-mismatch summary (which chroots failed vs.
    succeeded) is the most actionable single fact, so it's printed before
    the per-chroot compiler-error detail.
    """
    versions = versions or {}
    first = [True]
    for pkg in packages:
        pkg_log_dir = log_dir / pkg
        pkg_version = versions.get(pkg, "")

        copr_log = pkg_log_dir / "30-copr.log"
        _print_stage_issues(
            "copr", pkg, copr_log, analyze_copr_log(copr_log), first, pkg_version
        )

        chroot_summary = pkg_log_dir / "30-copr-chroots.log"
        _print_stage_issues(
            "copr/chroots",
            pkg,
            chroot_summary,
            analyze_copr_chroot_summary(chroot_summary),
            first,
            pkg_version,
        )

        for chroot_name, issues in analyze_copr_chroot_logs(pkg_log_dir).items():
            chroot_log = pkg_log_dir / f"31-copr-{chroot_name}.log"
            _print_stage_issues(
                f"copr/build:{chroot_name}", pkg, chroot_log, issues, first, pkg_version
            )
