"""License, build system, and version detection from source repos."""

import re
from pathlib import Path

LICENSE_MAP = [
    ("BSD 3-Clause", "BSD-3-Clause"),
    ("BSD 2-Clause", "BSD-2-Clause"),
    ("MIT License", "MIT"),
    ("MIT", "MIT"),
    ("Apache License", "Apache-2.0"),
    ("GNU LESSER GENERAL PUBLIC LICENSE", "LGPL-3.0-or-later"),
    ("GNU GENERAL PUBLIC LICENSE", "GPL-3.0-or-later"),
    ("ISC License", "ISC"),
    ("Mozilla Public License", "MPL-2.0"),
]

# pkg_check_modules() call (may span multiple lines)
PKG_CHECK_RE = re.compile(r"pkg_check_modules\s*\(([^)]+)\)", re.DOTALL)

# CMake keywords that appear inside pkg_check_modules() but are not package names
CMAKE_KEYWORDS = {
    "REQUIRED",
    "IMPORTED_TARGET",
    "QUIET",
    "NO_MODULE",
    "EXACT",
    "CONFIG",
    "MODULE",
    "STATIC",
    "GLOBAL",
}


def detect_license(repo: Path) -> str | None:
    """Detect SPDX license identifier from the repo's LICENSE file."""
    for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"):
        f = repo / name
        if not f.exists():
            continue
        first = (
            f.read_text(errors="replace").lstrip().splitlines()[0]
            if f.stat().st_size
            else ""
        )
        for needle, spdx in LICENSE_MAP:
            if needle.lower() in first.lower():
                return spdx
    return None


def detect_build_system(repo: Path) -> str | None:
    """Detect build system from repo root."""
    if (repo / "CMakeLists.txt").exists():
        return "cmake"
    if (repo / "meson.build").exists():
        return "meson"
    if (repo / "configure.ac").exists():
        return "autotools"
    if (repo / "Makefile").exists():
        return "make"
    return None


def extract_cmake_info(cmake_text: str) -> dict:
    """Extract summary and pkg-config deps from CMakeLists.txt text."""
    info: dict = {}

    desc_m = re.search(
        r'project\s*\([^)]*DESCRIPTION\s+"([^"]+)"', cmake_text, re.DOTALL
    )
    if desc_m:
        info["summary"] = desc_m.group(1)

    deps: list[str] = []
    for m in PKG_CHECK_RE.finditer(cmake_text):
        tokens = m.group(1).split()
        for i, tok in enumerate(tokens):
            if i == 0:  # variable name
                continue
            pkg = re.sub(r"[><=!]+.*$", "", tok)
            if not pkg or pkg in CMAKE_KEYWORDS:
                continue
            if re.match(r"^[a-z][a-z0-9\-\.]*$", pkg):
                deps.append(pkg)
    if deps:
        info["pkg_deps"] = deps

    return info


def extract_version(repo: Path) -> str | None:
    """Extract version from VERSION file if present."""
    version_file = repo / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return None
