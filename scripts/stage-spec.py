#!/usr/bin/env python3
"""Stage 1: Generate spec files for each package.

Reads packages.yaml and generates spec files per package, then records
success/failure in build-report.yaml.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE         Build only this package (optional, comma-separated)
  FEDORA_VERSION  Fedora version to target (default: 43)
  LOG_LEVEL       Logging level: DEBUG, INFO (default), WARNING, ERROR
"""

import logging
import os
import re
import subprocess
import sys

from lib.config import get_packager, setup_logging
from lib.github import build_changelog
from lib.gitmodules import get_changelog_info, parse_gitmodules, resolve_module
from lib.jinja_utils import create_jinja_env
from lib.paths import ROOT, get_package_log_dir
from lib.reporting import status
from lib.version import nvr
from lib.yaml_utils import (
    apply_os_overrides,
    get_packages,
    init_stage,
    load_repo_yaml,
    save_build_status,
)


def resolve_dep_versions(build_requires: list) -> list:
    """Return list of {name, version} for build deps from enabled repos."""
    results = []
    for dep in build_requires:
        req = re.split(r"\s*[><=!]", dep)[0].strip()
        if not req or req.startswith("%"):
            continue
        try:
            out = subprocess.run(
                [
                    "dnf",
                    "repoquery",
                    "--latest-limit",
                    "1",
                    "--queryformat",
                    "%{VERSION}",
                    req,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            version = out.stdout.strip() if out.returncode == 0 else None
        except Exception:
            version = None
        if version:
            results.append({"name": req, "version": version})
    return results


def generate_spec(
    pkg: str, pkg_meta: dict, all_packages: dict, fedora_version: str
) -> str:
    """Generate spec file content for package using Jinja2 template."""
    try:
        jinja = create_jinja_env()
        repo = load_repo_yaml()
        packager = get_packager()

        source = pkg_meta.get("source", {})
        build = pkg_meta.get("build", {})
        rpm = pkg_meta.get("rpm", {})

        # Build changelog info from submodule if available
        changelog_info = None
        if (ROOT / ".gitmodules").exists():
            gitmodules = parse_gitmodules(ROOT / ".gitmodules")
            module = resolve_module(gitmodules, pkg)
            if module:
                submodule_path = ROOT / module["path"]
                version = str(pkg_meta.get("version", ""))
                commit_meta = source.get("commit")
                commit_hash = (
                    commit_meta.get("full") if isinstance(commit_meta, dict) else None
                )
                changelog_info = get_changelog_info(
                    submodule_path, version, commit_hash
                )

        # Build changelog object (simplified version of gen-spec.py)
        release = pkg_meta.get("release", 1)
        changelog = build_changelog(
            changelog_info,
            str(pkg_meta.get("version", "")),
            release,
            packager,
            repo.get("source_url"),
            repo.get("copr_url"),
        )

        # Extract and normalize build fields
        build_system = build.get("system", "cmake")
        build_commands = build.get("commands", [])
        install_commands = build.get("install", [])

        # Default build/install commands by system
        BUILD_SYSTEMS = {
            "cmake": ("%cmake\n%cmake_build", "%cmake_install"),
            "meson": ("%meson\n%meson_build", "%meson_install"),
            "autotools": ("%configure\n%make_build", "%make_install"),
            "configure": ("./configure\n%make_build", "%make_install"),
            "make": ("make %{?_smp_mflags}", "make install DESTDIR=%{buildroot}"),
            "python": ("%pyproject_build", "%pyproject_install"),
        }

        # Build the build command
        if build_commands:
            build_cmd = "\n".join(build_commands)
        elif (
            build_system == "configure"
            and build.get("configure_flags")
            and not build_commands
        ):
            flags = " ".join(build["configure_flags"])
            build_cmd = f"./configure {flags}\n%make_build"
        else:
            build_cmd = BUILD_SYSTEMS.get(build_system, BUILD_SYSTEMS["cmake"])[0]

        # Build the install command
        if install_commands:
            install_cmd = "\n".join(install_commands)
        else:
            install_cmd = BUILD_SYSTEMS.get(build_system, BUILD_SYSTEMS["cmake"])[1]

        # Build devel package info
        raw_devel = pkg_meta.get("devel")
        devel = (
            {
                "requires": [r for r in raw_devel.get("requires", []) if r is not None],
                "files": [f for f in raw_devel.get("files", []) if f is not None],
            }
            if raw_devel
            else None
        )

        context = {
            "name": pkg.lower(),
            "version": pkg_meta.get("version", ""),
            "release": release,
            "summary": pkg_meta.get("summary", ""),
            "license": pkg_meta.get("license", ""),
            "buildarch": rpm.get("buildarch"),
            "commit": source.get("commit"),
            "source_name": pkg_meta.get("source_name") or source.get("name"),
            "url": pkg_meta.get("url", ""),
            "sources": source.get("archives", []),
            "patches": source.get("patches", []),
            "bundled_deps": source.get("bundled_deps", []),
            "source_dir": pkg_meta.get("source_dir"),
            "build_requires": pkg_meta.get("build_requires", []),
            "requires": pkg_meta.get("requires", []),
            "description": pkg_meta.get("description", "").strip(),
            "prep_commands": build.get("prep", []),
            "build_cmd": build_cmd,
            "install_cmd": install_cmd,
            "files": [
                f
                for f in pkg_meta.get("files", [f"%{{_bindir}}/{pkg}"])
                if f is not None
            ],
            "no_debug_package": rpm.get("no_debug_package", False),
            "no_lto": build.get("no_lto", False),
            "changelog": changelog,
            "devel": devel,
            "dep_versions": resolve_dep_versions(pkg_meta.get("build_requires", [])),
        }

        template = jinja.get_template("spec.j2")
        return template.render(**context)
    except Exception as e:
        raise RuntimeError(f"Failed to generate spec for {pkg}: {e}") from e


def run_for_package(
    pkg: str,
    meta: dict,
    all_packages: dict,
    build_status: dict,
    fedora_version: str,
) -> bool:
    """Run spec generation for a single package. Return True on success/skip, False on failure.

    Updates build_status["stages"]["spec"][pkg] in-place.
    Does not call save_build_status().
    """
    meta = apply_os_overrides(meta, fedora_version)
    if meta.get("_skip"):
        print(f"  [skip] {pkg} (fedora:{fedora_version} skip)")
        build_status["stages"]["spec"][pkg] = {
            "state": "skipped",
            "version": None,
            "force_run": False,
        }
        return True

    ver = nvr(str(meta["version"]), meta.get("release", 1), fedora_version)
    pkg_log_dir = get_package_log_dir(pkg)
    pkg_log_dir.mkdir(parents=True, exist_ok=True)
    log = pkg_log_dir / "00-spec.log"
    log.unlink(missing_ok=True)

    print(f"  [RUN]  spec: {pkg}", flush=True)

    try:
        spec_content = generate_spec(pkg, meta, all_packages, fedora_version)
        pkg_name = pkg.lower()
        spec_file = ROOT / "packages" / pkg_name / f"{pkg_name}.spec"
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        spec_file.write_text(spec_content)

        with open(log, "w") as fh:
            fh.write(f"Generated {spec_file}\n")
            fh.write("[exit: 0]\n")

        ok = True
    except Exception as e:
        with open(log, "w") as fh:
            fh.write(f"Error: {e}\n[exit: 1]\n")
        ok = False

    state = "success" if ok else "failed"
    status("spec", pkg, "ok" if ok else "fail")

    entry: dict = {
        "state": state,
        "version": ver,
        "log": str(log.relative_to(ROOT)),
        "force_run": False,
    }
    if "devel" in meta:
        entry["subpackages"] = {"devel": {"state": state, "version": ver}}
    build_status["stages"]["spec"][pkg] = entry

    return ok


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")

    packages, build_status = init_stage("spec")
    all_packages = get_packages()

    failed = False
    print("\n=== spec ===")
    for pkg, meta in packages.items():
        if not run_for_package(pkg, meta, all_packages, build_status, fedora_version):
            failed = True
        save_build_status(build_status)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        setup_logging()
        main()
    except KeyboardInterrupt:
        logging.warning("User Interrupted.")
        sys.exit(130)
