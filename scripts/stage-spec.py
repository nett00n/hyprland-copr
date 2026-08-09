#!/usr/bin/env python3
"""Stage 1: Generate spec files for each package.

Reads packages.yaml and generates spec files per package, then records
success/failure in build-report.db.

Must be run inside the rpm toolbox container (invoked via Makefile).

Environment variables:
  PACKAGE         Build only this package (optional, comma-separated)
  FEDORA_VERSION  Fedora version to target (default: 43)
  MOCK_CHROOT     Override mock chroot (default: fedora-{FEDORA_VERSION}-x86_64)
  LOG_LEVEL       Logging level: DEBUG, INFO (default), WARNING, ERROR
"""

import logging
import os
import re
import subprocess
import sys

from lib import build_db
from lib.build_systems import BUILD_SYSTEMS
from lib.config import get_packager, setup_logging
from lib.github import build_changelog
from lib.gitmodules import get_changelog_info, parse_gitmodules, resolve_module
from lib.jinja_utils import create_jinja_env
from lib.paths import ARCH, DISTRO, ROOT, get_package_log_dir, resolve_target
from lib.reporting import status
from lib.spec_utils import process_archive_urls
from lib.version import nvr
from lib.yaml_utils import (
    apply_os_overrides,
    get_packages,
    load_repo_yaml,
    prepare_stage,
)


def resolve_dep_versions(build_requires: list) -> list:
    """Return list of {name, version} for build deps from deterministic repos.

    Uses standard Fedora repos only (fedora, fedora-updates) to ensure
    consistent results across builds. Skips packages not found in these repos.
    """
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
                    "--repo=fedora",
                    "--repo=fedora-updates",
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

        # Python packages: %pyproject_save_files pairs with %files -f %{pyproject_files}
        save_files = build.get("save_files")
        files_from = None
        if save_files:
            install_cmd += f"\n%pyproject_save_files -L -a {save_files}"
            files_from = "%{pyproject_files}"

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

        # Prepare prep commands (including vendor tarball extraction for cargo)
        prep_commands = build.get("prep", [])
        if build_system == "cargo":
            archives = source.get("archives", [])
            if len(archives) >= 2 and "vendor" in archives[1]:
                prep_commands = ["tar xf %{SOURCE1}"] + prep_commands

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
            "sources": process_archive_urls(
                source.get("archives", []),
                pkg_meta.get("url", ""),
                pkg.lower(),
                source.get("commit")
                if isinstance(source.get("commit"), dict)
                else None,
                str(pkg_meta.get("version", "")),
            ),
            "patches": source.get("patches", []),
            "bundled_deps": source.get("bundled_deps", []),
            "source_dir": pkg_meta.get("source_dir"),
            "build_requires": pkg_meta.get("build_requires", []),
            "requires": pkg_meta.get("requires", []),
            "recommends": pkg_meta.get("recommends", []),
            "description": pkg_meta.get("description", "").strip(),
            "prep_commands": prep_commands,
            "build_cmd": build_cmd,
            "install_cmd": install_cmd,
            "files": [
                f
                for f in pkg_meta.get("files", [f"%{{_bindir}}/{pkg}"])
                if f is not None
            ],
            "files_from": files_from,
            "no_debug_package": rpm.get("no_debug_package", False),
            "no_lto": build.get("no_lto", False),
            "changelog": changelog,
            "devel": devel,
            "dep_versions": resolve_dep_versions(pkg_meta.get("build_requires", [])),
            "project_packages": list(all_packages.keys()),
        }

        template = jinja.get_template("spec.j2")
        return template.render(**context)
    except Exception as e:
        raise RuntimeError(f"Failed to generate spec for {pkg}: {e}") from e


def run_for_package(
    pkg: str,
    meta: dict,
    all_packages: dict,
    fedora_version: str,
    target: str,
    run_id: int,
) -> bool:
    """Run spec generation for a single package. Return True on success/skip, False on failure.

    Writes the spec stage row for `pkg`.
    """
    meta = apply_os_overrides(meta, fedora_version)
    if meta.get("_skip"):
        print(f"  [skip] {pkg} (fedora:{fedora_version} skip)")
        build_db.set_stage(
            pkg, "spec", target, run_id, "skipped", reason="config: skip"
        )
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

    build_db.set_stage(
        pkg,
        "spec",
        target,
        run_id,
        state,
        version=ver,
        log=str(log.relative_to(ROOT)),
        has_devel=1 if "devel" in meta else 0,
    )

    return ok


def main() -> None:
    fedora_version = os.environ.get("FEDORA_VERSION", "43")
    mock_chroot_override = os.environ.get("MOCK_CHROOT", "")
    target = resolve_target(fedora_version, mock_chroot_override)
    proceed = os.environ.get("PROCEED_BUILD", "").lower() == "true"

    run_id = build_db.start_run(
        target,
        DISTRO,
        fedora_version,
        ARCH,
        package_filter=os.environ.get("PACKAGE", ""),
    )

    packages = prepare_stage("spec", target, proceed)
    all_packages = get_packages()

    failed = False
    print("\n=== spec ===")
    for pkg, meta in packages.items():
        if not run_for_package(pkg, meta, all_packages, fedora_version, target, run_id):
            failed = True

    build_db.finish_run(run_id, "failed" if failed else "ok")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        setup_logging()
        main()
    except KeyboardInterrupt:
        logging.warning("User Interrupted.")
        sys.exit(130)
