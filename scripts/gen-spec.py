#!/usr/bin/env python3
"""Generate RPM spec files from packages.yaml + templates/spec.j2.

Usage:
    python3 scripts/gen-spec.py              # generate all packages
    python3 scripts/gen-spec.py hyprpaper    # generate one package
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from lib.gitmodules import get_changelog_info, parse_gitmodules
from lib.jinja_utils import create_jinja_env
from lib.paths import GITMODULES, ROOT
from lib.yaml_utils import get_packages, load_packages_yaml


def get_packager() -> str:
    try:
        name = subprocess.check_output(
            ["git", "config", "user.name"], text=True
        ).strip()
        email = subprocess.check_output(
            ["git", "config", "user.email"], text=True
        ).strip()
        return f"{name} <{email}>"
    except Exception:
        return "Packager <packager@example.com>"


def fetch_github_release(github_url: str, version: str) -> dict | None:
    m = re.match(r"https://github\.com/([^/]+/[^/]+)", github_url)
    if not m:
        return None
    repo = m.group(1)
    api_url = f"https://api.github.com/repos/{repo}/releases/tags/v{version}"
    req = urllib.request.Request(
        api_url, headers={"Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def build_changelog(
    release_info: dict | None,
    version: str,
    release: int | str,
    packager: str,
    source_url: str | None = None,
    copr_url: str | None = None,
) -> dict:
    """Return structured changelog data for the Jinja2 template."""
    if release_info and release_info.get("published_at"):
        dt = datetime.fromisoformat(
            release_info["published_at"].replace("Z", "+00:00")
        )
    else:
        dt = datetime.now(timezone.utc)

    # Normalise tag/commit across local-git and GitHub-API sources
    tag = (release_info.get("tag") or release_info.get("tag_name")) if release_info else None
    commit = release_info.get("commit") if release_info else None

    # Parse body into clean note strings (strip markdown bullets/headings)
    notes: list[str] = []
    body = release_info.get("body") if release_info else None
    if body:
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(("- ", "* ", "• ")):
                notes.append(line[2:].strip())
            else:
                notes.append(line)
    if not notes:
        notes.append(f"Update to {version}")

    return {
        "date": dt.strftime("%a %b %d %Y"),
        "packager": packager,
        "version": str(version),
        "release": release,
        "tag": tag,
        "commit": commit,
        "notes": notes,
        "source_url": source_url,
        "copr_url": copr_url,
    }


BUILD_SYSTEMS = {
    "cmake": ("%cmake\n%cmake_build", "%cmake_install"),
    "meson": ("%meson\n%meson_build", "%meson_install"),
    "autotools": ("%configure\n%make_build", "%make_install"),
    "make": ("make %{?_smp_mflags}", "make install DESTDIR=%{buildroot}"),
    "python": ("%pyproject_build", "%pyproject_install"),
}


def build_context(
    name: str,
    pkg: dict,
    packager: str,
    url_to_submodule: dict,
    source_url: str | None = None,
    copr_url: str | None = None,
) -> dict:
    build_system = pkg.get("build_system", "cmake")
    build_cmd, install_cmd = BUILD_SYSTEMS.get(build_system, BUILD_SYSTEMS["cmake"])

    if "build_commands" in pkg:
        build_cmd = "\n".join(pkg["build_commands"])
    if "install_commands" in pkg:
        install_cmd = "\n".join(pkg["install_commands"])

    version = pkg["version"]
    release = pkg.get("release", 1)
    pkg_url = pkg.get("url", "").rstrip("/")
    submodule_path = url_to_submodule.get(pkg_url) or url_to_submodule.get(
        pkg_url.removesuffix(".git")
    )
    if submodule_path:
        commit_meta = pkg.get("commit")
        commit_hash = commit_meta.get("full") if isinstance(commit_meta, dict) else None
        release_info = get_changelog_info(submodule_path, str(version), commit_hash)
    else:
        release_info = None
    if release_info is None:
        release_info = fetch_github_release(pkg_url, version)
    changelog = build_changelog(release_info, version, release, packager, source_url, copr_url)

    bundled_deps = []
    extra_prep = []
    num_main_sources = len(pkg.get("sources", []))
    for i, dep in enumerate(pkg.get("bundled_deps", [])):
        dep_name = dep["name"]
        dep_version = dep["version"]
        source_index = num_main_sources + i
        extracted_dir = f"{dep_name}-{dep_version}"
        target_dir = f"{dep_name}-src"
        cmake_var = dep.get("cmake_var", dep_name.upper())
        local_filename = f"{dep_name}-{dep_version}.tar.gz"
        bundled_deps.append(
            {
                "name": dep_name,
                "version": dep_version,
                "url": f"{dep['url']}#/{local_filename}",
                "source_index": source_index,
                "cmake_var": cmake_var,
            }
        )
        extra_prep += [
            f"tar xf %{{SOURCE{source_index}}}",
            f"mv {extracted_dir} {target_dir}",
        ]

    if bundled_deps and build_system == "cmake" and "build_commands" not in pkg:
        src_subdir = "%{name}-%{commit}" if pkg.get("commit") else "%{name}-%{version}"
        flags = ["-DFETCHCONTENT_FULLY_DISCONNECTED=ON"] + [
            f"-DFETCHCONTENT_SOURCE_DIR_{d['cmake_var']}="
            f"%{{_builddir}}/{src_subdir}/{d['name']}-src"
            for d in bundled_deps
        ]
        flags_str = " \\\n    ".join(flags)
        build_cmd = f"%cmake \\\n    {flags_str}\n%cmake_build"

    prep_commands = extra_prep + pkg.get("prep_commands", [])

    return {
        "name": name,
        "version": version,
        "release": release,
        "summary": pkg["summary"],
        "license": pkg["license"],
        "buildarch": pkg.get("buildarch"),
        "commit": pkg.get("commit"),
        "source_name": pkg.get("source_name"),
        "url": pkg["url"],
        "sources": pkg["sources"],
        "bundled_deps": bundled_deps,
        "build_requires": pkg.get("build_requires", []),
        "requires": pkg.get("requires", []),
        "description": pkg["description"].strip(),
        "prep_commands": prep_commands,
        "build_cmd": build_cmd,
        "install_cmd": install_cmd,
        "files": [
            f for f in pkg.get("files", [f"%{{_bindir}}/{name}"]) if f is not None
        ],
        "no_debug_package": pkg.get("no_debug_package", False),
        "changelog": changelog,
        "devel": {
            "requires": [r for r in raw_devel.get("requires", []) if r is not None],
            "files": [f for f in raw_devel.get("files", []) if f is not None],
        }
        if (raw_devel := pkg.get("devel"))
        else None,
    }


def main() -> None:
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

    yaml_data = load_packages_yaml()
    packages = yaml_data.get("packages") or {}
    if not packages:
        sys.exit("error: no packages defined in packages.yaml")
    repo = yaml_data.get("repo") or {}
    source_url = repo.get("source_url") or None
    copr_url = repo.get("copr_url") or None

    target = args.package
    if target and target not in packages:
        sys.exit(f"error: package '{target}' not found in packages.yaml")

    env = create_jinja_env()
    template = env.get_template("spec.j2")
    packager = get_packager()

    url_to_submodule: dict[str, object] = {}
    if GITMODULES.exists():
        for mod in parse_gitmodules(GITMODULES):
            url = mod["url"].rstrip("/")
            path = ROOT / mod["path"]
            url_to_submodule[url] = path
            url_to_submodule[url.removesuffix(".git")] = path

    for name, pkg in packages.items():
        if target and name != target:
            continue
        pkg_name = name.lower()
        spec_dir = ROOT / "packages" / pkg_name
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_path = spec_dir / f"{pkg_name}.spec"
        spec_path.write_text(
            template.render(build_context(pkg_name, pkg, packager, url_to_submodule, source_url, copr_url))
        )
        print(f"  generated  {spec_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
