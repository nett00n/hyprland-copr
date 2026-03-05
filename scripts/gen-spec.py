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
from lib.jinja_utils import create_jinja_env
from lib.paths import ROOT
from lib.yaml_utils import get_packages


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


def format_changelog(
    release: dict | None, version: str, release_num: int, packager: str
) -> str:
    if release and release.get("published_at"):
        dt = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
    else:
        dt = datetime.now(timezone.utc)
    date_str = dt.strftime("%a %b %d %Y")
    header = f"* {date_str} {packager} - {version}-{release_num}"
    if release and release.get("body"):
        lines = []
        for line in release["body"].splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(("- ", "* ", "• ")):
                lines.append(f"- {line[2:].strip()}")
            else:
                lines.append(f"- {line}")
        body = "\n".join(lines) if lines else f"- Update to {version}"
    else:
        body = f"- Update to {version}"
    return f"{header}\n{body}"


BUILD_SYSTEMS = {
    "cmake": ("%cmake\n%cmake_build", "%cmake_install"),
    "meson": ("%meson\n%meson_build", "%meson_install"),
    "autotools": ("%configure\n%make_build", "%make_install"),
    "make": ("make %{?_smp_mflags}", "make install DESTDIR=%{buildroot}"),
}


def build_context(name: str, pkg: dict, packager: str) -> dict:
    build_system = pkg.get("build_system", "cmake")
    build_cmd, install_cmd = BUILD_SYSTEMS.get(build_system, BUILD_SYSTEMS["cmake"])

    if "build_commands" in pkg:
        build_cmd = "\n".join(pkg["build_commands"])
    if "install_commands" in pkg:
        install_cmd = "\n".join(pkg["install_commands"])

    version = pkg["version"]
    release = pkg.get("release", 1)
    release_info = fetch_github_release(pkg.get("url", ""), version)
    changelog = format_changelog(release_info, version, release, packager)

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

    packages = get_packages()
    target = args.package
    if target and target not in packages:
        sys.exit(f"error: package '{target}' not found in packages.yaml")

    env = create_jinja_env()
    template = env.get_template("spec.j2")
    packager = get_packager()

    for name, pkg in packages.items():
        if target and name != target:
            continue
        pkg_name = name.lower()
        spec_dir = ROOT / "packages" / pkg_name
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_path = spec_dir / f"{pkg_name}.spec"
        spec_path.write_text(template.render(build_context(pkg_name, pkg, packager)))
        print(f"  generated  {spec_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
