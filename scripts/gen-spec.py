#!/usr/bin/env python3
"""Generate RPM spec files from packages.yaml + templates/spec.j2.

Usage:
    python3 scripts/gen-spec.py              # generate all packages
    python3 scripts/gen-spec.py hyprpaper    # generate one package
"""

import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("error: PyYAML not installed — run: pip install -r requirements.txt")

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError:
    sys.exit("error: Jinja2 not installed — run: pip install -r requirements.txt")


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

    return {
        "name": name,
        "version": version,
        "release": release,
        "summary": pkg["summary"],
        "license": pkg["license"],
        "url": pkg["url"],
        "sources": pkg["sources"],
        "build_requires": pkg.get("build_requires", []),
        "requires": pkg.get("requires", []),
        "description": pkg["description"].strip(),
        "prep_commands": pkg.get("prep_commands", []),
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
    repo_root = Path(__file__).resolve().parent.parent

    packages_yaml = repo_root / "packages.yaml"
    if not packages_yaml.exists():
        sys.exit(f"error: {packages_yaml} not found")

    env = Environment(
        loader=FileSystemLoader(repo_root / "templates"),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    template = env.get_template("spec.j2")

    with open(packages_yaml) as fh:
        data = yaml.safe_load(fh)

    packages: dict = data.get("packages") or {}
    if not packages:
        sys.exit("error: no packages defined in packages.yaml")

    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target and target not in packages:
        sys.exit(f"error: package '{target}' not found in packages.yaml")

    packager = get_packager()

    for name, pkg in packages.items():
        if target and name != target:
            continue
        spec_dir = repo_root / "packages" / name
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_path = spec_dir / f"{name}.spec"
        spec_path.write_text(template.render(build_context(name, pkg, packager)))
        print(f"  generated  {spec_path.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
