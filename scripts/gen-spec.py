#!/usr/bin/env python3
"""Generate RPM spec files from packages.yaml + templates/spec.j2.

Usage:
    python3 scripts/gen-spec.py              # generate all packages
    python3 scripts/gen-spec.py hyprpaper    # generate one package
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from lib.gitmodules import get_changelog_info, parse_gitmodules
from lib.jinja_utils import create_jinja_env
from lib.paths import GITMODULES, GITHUB_RELEASE_CACHE, ROOT
from lib.yaml_utils import apply_os_overrides, get_packages, load_repo_yaml


def get_packager() -> str:
    # 1. Try environment variables (highest priority)
    packager = os.environ.get("PACKAGER")
    if packager:
        return packager

    env_var_name = os.environ.get("PACKAGER_NAME", "").strip()
    env_var_email = os.environ.get("PACKAGER_EMAIL", "").strip()
    if env_var_name and env_var_email:
        return f"{env_var_name} <{env_var_email}>"

    # 2. Try .env file
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        env_name: str = ""
        env_email: str = ""
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("PACKAGER="):
                    return line.split("=", 1)[1].strip().strip("\"'")
                elif line.startswith("PACKAGER_NAME="):
                    env_name = line.split("=", 1)[1].strip().strip("\"'")
                elif line.startswith("PACKAGER_EMAIL="):
                    env_email = line.split("=", 1)[1].strip().strip("\"'")
        if env_name and env_email:
            return f"{env_name} <{env_email}>"

    # 3. Try gitconfig (lowest priority)
    try:
        git_name = subprocess.check_output(
            ["git", "config", "user.name"], text=True
        ).strip()
        git_email = subprocess.check_output(
            ["git", "config", "user.email"], text=True
        ).strip()
        if git_name and git_email:
            return f"{git_name} <{git_email}>"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # 4. Default fallback
    return "Packager <packager@example.com>"


CACHE_TTL = 7 * 24 * 3600  # 7 days


def _cache_key(github_url: str, version: str) -> str:
    m = re.match(r"https://github\.com/([^/]+/[^/]+)", github_url)
    return f"{m.group(1)}@{version}" if m else f"{github_url}@{version}"


def load_release_cache(url: str, version: str) -> dict | None:
    if not GITHUB_RELEASE_CACHE.exists():
        return None
    try:
        data = json.loads(GITHUB_RELEASE_CACHE.read_text())
        entry = data.get(_cache_key(url, version))
        if entry and time.time() - entry["timestamp"] < CACHE_TTL:
            return entry["data"]
    except (json.JSONDecodeError, KeyError, OSError):
        pass
    return None


def save_release_cache(url: str, version: str, release: dict) -> None:
    GITHUB_RELEASE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = (
            json.loads(GITHUB_RELEASE_CACHE.read_text())
            if GITHUB_RELEASE_CACHE.exists()
            else {}
        )
    except (json.JSONDecodeError, OSError):
        data = {}
    data[_cache_key(url, version)] = {"data": release, "timestamp": int(time.time())}
    GITHUB_RELEASE_CACHE.write_text(json.dumps(data, indent=2))


GITHUB_RETRIES = 3
GITHUB_RETRY_PAUSE = 10  # seconds


def fetch_github_release(github_url: str, version: str) -> dict | None:
    m = re.match(r"https://github\.com/([^/]+/[^/]+)", github_url)
    if not m:
        return None
    repo = m.group(1)
    api_url = f"https://api.github.com/repos/{repo}/releases/tags/v{version}"
    req = urllib.request.Request(
        api_url, headers={"Accept": "application/vnd.github+json"}
    )
    for attempt in range(1, GITHUB_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            # Don't retry on permanent client errors (4xx) except 429 (rate limit)
            if 400 <= e.code < 500 and e.code != 429:
                print(
                    f"warning: failed to fetch {api_url}: HTTP {e.code}",
                    file=sys.stderr,
                )
                return None
            # Retry on transient errors: 429, 5xx, network errors
            if attempt < GITHUB_RETRIES:
                print(
                    f"warning: github fetch attempt {attempt} failed (HTTP {e.code}), retrying in {GITHUB_RETRY_PAUSE}s",
                    file=sys.stderr,
                )
                time.sleep(GITHUB_RETRY_PAUSE)
            else:
                print(
                    f"warning: failed to fetch {api_url}: HTTP {e.code}",
                    file=sys.stderr,
                )
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            # Retry on network/timeout errors
            if attempt < GITHUB_RETRIES:
                print(
                    f"warning: github fetch attempt {attempt} failed ({e}), retrying in {GITHUB_RETRY_PAUSE}s",
                    file=sys.stderr,
                )
                time.sleep(GITHUB_RETRY_PAUSE)
            else:
                print(f"warning: failed to fetch {api_url}: {e}", file=sys.stderr)
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
        dt = datetime.fromisoformat(release_info["published_at"].replace("Z", "+00:00"))
    else:
        dt = datetime.now(timezone.utc)

    # Normalise tag/commit across local-git and GitHub-API sources
    tag = (
        (release_info.get("tag") or release_info.get("tag_name"))
        if release_info
        else None
    )
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
    # Hand-written configure scripts (no autoconf); flags come from configure_flags in packages.yaml
    "configure": ("./configure\n%make_build", "%make_install"),
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

    version = pkg["version"]
    release = pkg.get("release", 1)
    pkg_url = pkg.get("url", "").rstrip("/")
    submodule_path = url_to_submodule.get(pkg_url) or url_to_submodule.get(
        pkg_url.removesuffix(".git")
    )
    if submodule_path:
        commit_meta = source.get("commit")
        commit_hash = commit_meta.get("full") if isinstance(commit_meta, dict) else None
        release_info = get_changelog_info(submodule_path, str(version), commit_hash)
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
    for i, dep in enumerate(source.get("bundled_deps", [])):
        dep_name = dep["name"]
        dep_version = dep["version"]
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

    return {
        "name": name,
        "version": version,
        "release": release,
        "summary": pkg["summary"],
        "license": pkg["license"],
        "buildarch": rpm.get("buildarch"),
        "commit": source.get("commit"),
        "source_name": source.get("name"),
        "url": pkg["url"],
        "sources": source.get("archives", []),
        "patches": source.get("patches", []),
        "bundled_deps": bundled_deps,
        "build_requires": pkg.get("build_requires") or [],
        "requires": pkg.get("requires") or [],
        "description": pkg["description"].strip(),
        "prep_commands": prep_commands,
        "build_cmd": build_cmd,
        "install_cmd": install_cmd,
        "files": [
            f for f in pkg.get("files", [f"%{{_bindir}}/{name}"]) if f is not None
        ],
        "no_debug_package": rpm.get("no_debug_package", False),
        "no_lto": build.get("no_lto", False),
        "changelog": changelog,
        "devel": {
            "requires": [r for r in raw_devel.get("requires", []) if r is not None],
            "files": [f for f in raw_devel.get("files", []) if f is not None],
        }
        if (raw_devel := pkg.get("devel"))
        else None,
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

    fedora_version = os.environ.get("FEDORA_VERSION", "43")
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
        pkg = apply_os_overrides(pkg, fedora_version)
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
                    pkg_name, pkg, packager, url_to_submodule, source_url, copr_url
                )
            )
        )
        print(f"  generated  {spec_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
