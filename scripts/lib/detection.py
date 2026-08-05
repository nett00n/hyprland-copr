"""License, build system, and version detection from source repos."""

import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore

# Meson dependency() call — captures name and the rest of the argument list
MESON_DEP_RE = re.compile(r"dependency\s*\(\s*'([^']+)'([^)]*)\)", re.DOTALL)

# System/virtual deps that have no pkg-config equivalent
MESON_SKIP_DEPS = {"threads", ""}

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
    if (repo / "Cargo.toml").exists():
        return "cargo"
    if (repo / "configure.ac").exists():
        return "autotools"
    if (repo / "configure").exists() and (repo / "Makefile.in").exists():
        return "autotools"
    if (repo / "pyproject.toml").exists() or (repo / "setup.py").exists():
        return "python"
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


def extract_meson_info(meson_text: str) -> dict:
    """Extract summary and required pkg-config deps from meson.build text."""
    info: dict = {}

    desc_m = re.search(
        r"project\s*\([^)]*description\s*:\s*'([^']+)'",
        meson_text,
        re.DOTALL | re.IGNORECASE,
    )
    if desc_m:
        info["summary"] = desc_m.group(1)

    deps: list[str] = []
    for m in MESON_DEP_RE.finditer(meson_text):
        name = m.group(1)
        args = m.group(2)
        if name in MESON_SKIP_DEPS:
            continue
        # Skip explicitly optional or conditionally optional deps
        if re.search(r"required\s*:\s*false", args):
            continue
        if re.search(r"required\s*:\s*get_option\s*\(", args):
            continue
        if name not in deps:
            deps.append(name)

    if deps:
        info["pkg_deps"] = deps

    return info


# PEP 517 build-backend -> extra BuildRequires needed to invoke %pyproject_wheel
PYTHON_BACKEND_REQUIRES = {
    "setuptools.build_meta": "python3-setuptools",
    "poetry.core.masonry.api": "python3-poetry-core",
    "hatchling.build": "python3-hatchling",
    "flit_core.buildapi": "python3-flit-core",
    "pdm.backend": "python3-pdm-backend",
}


def extract_python_info(repo: Path) -> dict:
    """Extract summary, dist name, top-level module name, and build backend
    from pyproject.toml (PEP 621 / Poetry) or a legacy setup.py.
    """
    info: dict = {}
    dist_name: str | None = None

    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text(errors="replace"))
        except tomllib.TOMLDecodeError:
            data = {}
        build_backend = data.get("build-system", {}).get("build-backend")
        if build_backend:
            info["build_backend"] = build_backend
        project = data.get("project", {})
        if project.get("description"):
            info["summary"] = project["description"]
        if project.get("name"):
            dist_name = project["name"]
        poetry = data.get("tool", {}).get("poetry", {})
        if not info.get("summary") and poetry.get("description"):
            info["summary"] = poetry["description"]
        if not dist_name and poetry.get("name"):
            dist_name = poetry["name"]

    if not info.get("summary") or not dist_name:
        setup_py = repo / "setup.py"
        if setup_py.exists():
            text = setup_py.read_text(errors="replace")
            if not dist_name:
                m = re.search(r"""name\s*=\s*['"]([^'"]+)['"]""", text)
                if m:
                    dist_name = m.group(1)
            if not info.get("summary"):
                m = re.search(r"""description\s*=\s*['"]([^'"]+)['"]""", text)
                if m:
                    info["summary"] = m.group(1)

    module_name = _detect_python_module_name(repo, dist_name)
    if module_name:
        info["module_name"] = module_name

    return info


def _detect_python_module_name(repo: Path, dist_name: str | None) -> str | None:
    """Best-effort top-level importable module/package name, for %pyproject_save_files."""
    candidates = []
    if dist_name:
        candidates.append(dist_name.replace("-", "_"))
    candidates.append(repo.name.replace("-", "_"))
    for name in candidates:
        if (repo / name / "__init__.py").exists() or (repo / f"{name}.py").exists():
            return name
    return candidates[0] if candidates else None


def python_build_requires(build_backend: str | None) -> list[str]:
    """BuildRequires needed to run %pyproject_wheel/%pyproject_install for a given backend."""
    requires = ["python3-devel", "pyproject-rpm-macros", "python3-pip"]
    requires.append(
        PYTHON_BACKEND_REQUIRES.get(build_backend or "", "python3-setuptools")
    )
    return requires


def extract_version(repo: Path) -> str | None:
    """Extract version from VERSION file if present."""
    version_file = repo / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return None
