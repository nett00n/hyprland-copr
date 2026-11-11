#!/usr/bin/env python3
"""Generate RPM spec files from packages.yaml + templates/spec.j2.

Usage:
    python3 scripts/gen-spec.py              # generate all packages
    python3 scripts/gen-spec.py hyprpaper    # generate one package
"""

import argparse
import sys
from pathlib import Path

from lib.build_systems import BUILD_SYSTEMS
from lib.config import get_packager
from lib.github import (
    build_changelog,
    fetch_github_release,
    load_release_cache,
    save_release_cache,
)
from lib.jinja_utils import create_jinja_env
from lib.paths import ROOT
from lib.spec_utils import process_archive_urls
from lib.upstream import get_changelog_info, list_upstreams, mirror_path
from lib.yaml_utils import apply_os_overrides, get_packages, load_repo_yaml


# #BUG-0074: unique logic vs stage-spec.py -- bundled_deps Sources/cmake flags and
# build.subdir pushd wrapping; the duplicated GitHub/packager helpers now come from lib.
def build_context(
    name: str,
    pkg: dict,
    packager: str,
    url_to_mirror: dict,
    project_packages: list | None = None,
    source_url: str | None = None,
    copr_url: str | None = None,
) -> dict:
    source = pkg.get("source", {})
    build = pkg.get("build", {})
    rpm = pkg.get("rpm", {})

    build_system = build.get("system", "cmake")
    build_cmd, install_cmd = BUILD_SYSTEMS.get(build_system, BUILD_SYSTEMS["cmake"])

    if (
        build_system == "configure"
        and build.get("configure_flags")
        and not build.get("commands")
    ):
        flags = " ".join(build["configure_flags"])
        build_cmd = f"./configure {flags}\n%make_build"

    if build.get("commands"):
        build_cmd = "\n".join(build["commands"])
    if build.get("install"):
        install_cmd = "\n".join(build["install"])

    version = str(pkg["version"])
    release = pkg.get("release", 1)
    pkg_url = pkg.get("url", "").rstrip("/")
    mirror_dir = url_to_mirror.get(pkg_url) or url_to_mirror.get(
        pkg_url.removesuffix(".git")
    )
    if mirror_dir:
        commit_meta = source.get("commit")
        commit_hash = commit_meta.get("full") if isinstance(commit_meta, dict) else None
        release_info = get_changelog_info(mirror_dir, str(version), commit_hash)
    else:
        release_info = None
    if release_info is None:
        release_info = load_release_cache(pkg_url, version)
    if release_info is None:
        release_info = fetch_github_release(pkg_url, version)
        if release_info is not None:
            save_release_cache(pkg_url, version, release_info)
    changelog = build_changelog(
        release_info, version, release, packager, source_url, copr_url
    )

    bundled_deps = []
    extra_prep = []
    num_main_sources = len(source.get("archives", []))

    # Auto-detect vendor tarball for cargo builds
    if build_system == "cargo" and num_main_sources > 0:
        # Check if the second source looks like a vendor tarball
        archives = source.get("archives", [])
        if len(archives) >= 2 and "vendor" in archives[1]:
            extra_prep.append("tar xf %{SOURCE1}")

    for i, dep in enumerate(source.get("bundled_deps", [])):
        dep_name = dep["name"]
        dep_version = str(dep["version"])
        source_index = num_main_sources + i
        extracted_dir = f"{dep_name}-{dep_version}"
        target_dir = f"{dep_name}-src"
        cmake_var = dep.get("cmake_var", dep_name.upper())
        dep_source_subdir = dep.get("source_subdir", "")
        local_filename = f"{dep_name}-{dep_version}.tar.gz"
        bundled_deps.append(
            {
                "name": dep_name,
                "version": dep_version,
                "url": f"{dep['url']}#/{local_filename}",
                "source_index": source_index,
                "cmake_var": cmake_var,
                "source_subdir": dep_source_subdir,
            }
        )
        extra_prep += [
            f"tar xf %{{SOURCE{source_index}}}",
            f"mv {extracted_dir} {target_dir}",
        ]

    if bundled_deps and build_system == "cmake" and "commands" not in build:
        src_subdir = (
            "%{name}-%{commit}" if source.get("commit") else "%{name}-%{version}"
        )
        cmake_flags = ["-DFETCHCONTENT_FULLY_DISCONNECTED=ON"] + [
            f"-DFETCHCONTENT_SOURCE_DIR_{d['cmake_var']}="
            f"%{{_builddir}}/{src_subdir}/{d['name']}-src"
            + (f"/{d['source_subdir']}" if d.get("source_subdir") else "")
            for d in bundled_deps
        ]
        flags_str = " \\\n    ".join(cmake_flags)
        build_cmd = f"%cmake \\\n    {flags_str}\n%cmake_build"

    source_subdir = build.get("subdir", "")
    if source_subdir and not build.get("commands"):
        if build_system == "cmake":
            cmake_config, _, _ = build_cmd.rpartition("\n%cmake_build")
            build_cmd = f"pushd {source_subdir}\n{cmake_config}\npopd\n%cmake_build"
        elif build_system == "meson":
            meson_config, _, _ = build_cmd.rpartition("\n%meson_build")
            build_cmd = f"pushd {source_subdir}\n{meson_config}\npopd\n%meson_build"
        else:
            build_cmd = f"pushd {source_subdir}\n{build_cmd}\npopd"
    if (
        source_subdir
        and not build.get("install")
        and build_system not in ("cmake", "meson")
    ):
        install_cmd = f"pushd {source_subdir}\n{install_cmd}\npopd"

    prep_commands = extra_prep + build.get("prep", [])

    # Python packages: %pyproject_save_files pairs with %files -f %{pyproject_files}
    save_files = build.get("save_files")
    files_from = None
    if save_files:
        install_cmd += f"\n%pyproject_save_files -L -a {save_files}"
        files_from = "%{pyproject_files}"

    processed_archives = process_archive_urls(
        source.get("archives", []),
        pkg.get("url", ""),
        name,
        source.get("commit") if isinstance(source.get("commit"), dict) else None,
        str(version),
    )

    return {
        "name": name,
        "version": version,
        "release": release,
        "summary": pkg["summary"],
        "license": pkg["license"],
        "buildarch": rpm.get("buildarch"),
        "commit": source.get("commit"),
        "source_name": pkg.get("source_name") or source.get("name"),
        "source_dir": pkg.get("source_dir"),
        "url": pkg["url"],
        "sources": processed_archives,
        "patches": source.get("patches", []),
        "bundled_deps": bundled_deps,
        "build_requires": pkg.get("build_requires") or [],
        "requires": pkg.get("requires") or [],
        "recommends": pkg.get("recommends") or [],
        "conflicts": pkg.get("conflicts") or [],
        "provides": pkg.get("provides") or [],
        "description": pkg["description"].strip(),
        "prep_commands": prep_commands,
        "build_cmd": build_cmd,
        "install_cmd": install_cmd,
        "files": [
            f for f in pkg.get("files", [f"%{{_bindir}}/{name}"]) if f is not None
        ],
        "files_from": files_from,
        "no_debug_package": rpm.get("no_debug_package", False),
        "no_lto": build.get("no_lto", False),
        "changelog": changelog,
        "devel": {
            "requires": [r for r in raw_devel.get("requires", []) if r is not None],
            "files": [f for f in raw_devel.get("files", []) if f is not None],
        }
        if (raw_devel := pkg.get("devel"))
        else None,
        "dep_versions": [],
        "project_packages": project_packages or [],
    }


def main() -> None:
    import os

    parser = argparse.ArgumentParser(
        description="Generate RPM spec files from packages.yaml + templates/spec.j2."
    )
    parser.add_argument(
        "package",
        nargs="?",
        metavar="PACKAGE",
        help="generate spec for this package only (default: all)",
    )
    args = parser.parse_args()

    fedora_version = os.environ.get("FEDORA_VERSION", "44")
    packages = get_packages()
    repo = load_repo_yaml()
    source_url = repo.get("source_url") or None
    copr_url = repo.get("copr_url") or None

    target = args.package
    if target and target not in packages:
        sys.exit(f"error: package '{target}' not found in packages.yaml")

    env = create_jinja_env()
    template = env.get_template("spec.j2")
    packager = get_packager()

    # Changelog metadata is read straight from the bare mirror (#COPR-0004).
    url_to_mirror: dict[str, Path] = {}
    for mod in list_upstreams(packages):
        url = mod["url"].rstrip("/")
        path = mirror_path(mod["url"])
        url_to_mirror[url] = path
        url_to_mirror[url.removesuffix(".git")] = path

    for name, raw_pkg in packages.items():
        if target and name != target:
            continue
        pkg = apply_os_overrides(raw_pkg, fedora_version)
        if pkg.get("_skip"):
            print(f"  skipped   {name} (fedora:{fedora_version} skip)")
            continue
        pkg_name = name.lower()
        spec_dir = ROOT / "packages" / pkg_name
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_path = spec_dir / f"{pkg_name}.spec"
        spec_path.write_text(
            template.render(
                build_context(
                    pkg_name,
                    pkg,
                    packager,
                    url_to_mirror,
                    list(packages.keys()),
                    source_url,
                    copr_url,
                )
            )
        )
        print(f"  generated  {spec_path.relative_to(ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
