#!/usr/bin/env python3
"""Normalize paths in packages.yaml files sections between absolute paths and RPM macros.

By default converts absolute paths -> RPM macros.
Use --reverse to convert RPM macros -> absolute paths.

Usage:
    python3 scripts/normalize-paths.py                       # abs -> macros
    python3 scripts/normalize-paths.py --reverse             # macros -> abs
    python3 scripts/normalize-paths.py --dry-run             # preview only
    python3 scripts/normalize-paths.py --reverse --dry-run
"""

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("error: PyYAML not installed — run: pip install -r requirements.txt")

# Ordered longest-first so more-specific prefixes win when going abs -> macro.
# /usr/lib (non-arch) only has well-known sub-paths mapped; the base itself is
# intentionally omitted because on x86_64 %{_libdir} resolves to /usr/lib64,
# not /usr/lib.
PREFIXES: list[tuple[str, str]] = [
    ("/etc",                    "%{_sysconfdir}"),
    ("/run",                    "%{_rundir}"),
    ("/usr",                    "%{_prefix}"),
    ("/usr/bin",                "%{_bindir}"),
    ("/usr/include",            "%{_includedir}"),
    ("/usr/lib/systemd/system", "%{_unitdir}"),
    ("/usr/lib/systemd/user",   "%{_userunitdir}"),
    ("/usr/lib/sysusers.d",     "%{_sysusersdir}"),
    ("/usr/lib/tmpfiles.d",     "%{_tmpfilesdir}"),
    ("/usr/lib64",              "%{_libdir}"),
    ("/usr/libexec",            "%{_libexecdir}"),
    ("/usr/sbin",               "%{_sbindir}"),
    ("/usr/share",              "%{_datadir}"),
    ("/usr/share/doc",          "%{_docdir}"),
    ("/usr/share/info",         "%{_infodir}"),
    ("/usr/share/man",          "%{_mandir}"),
    ("/var",                    "%{_localstatedir}"),
    ("/var/lib",                "%{_sharedstatedir}"),
]


def normalize_abs_to_macro(path: str) -> str:
    """Replace an absolute path prefix with the most specific RPM macro."""
    for prefix, macro in PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return macro + path[len(prefix):]
    return path


def normalize_macro_to_abs(path: str) -> str:
    """Replace a leading RPM macro with its absolute path equivalent."""
    for prefix, macro in PREFIXES:
        macro_slash = macro + "/"
        if path == macro:
            return prefix
        if path.startswith(macro_slash):
            return prefix + path[len(macro):]
    return path


def normalize_file_entry(entry: str, reverse: bool) -> str:
    """Normalize a file entry, handling leading RPM directives.

    Forward (default):
        /usr/bin/foo            -> %{_bindir}/foo
        %dir /usr/share/bar     -> %dir %{_datadir}/bar
        %{_bindir}/baz          -> %{_bindir}/baz  (unchanged)
        %license LICENSE        -> %license LICENSE (unchanged)

    Reverse (--reverse):
        %{_bindir}/foo          -> /usr/bin/foo
        %dir %{_datadir}/bar    -> %dir /usr/share/bar
        /usr/bin/baz            -> /usr/bin/baz    (unchanged)
        %license LICENSE        -> %license LICENSE (unchanged)
    """
    if reverse:
        # Match optional leading RPM directives then a %{macro} path
        m = re.match(r"^((?:%[^\s{][^\s]*\s+)*)(%\{[^}]+\}.*)", entry)
        if m:
            return m.group(1) + normalize_macro_to_abs(m.group(2))
    else:
        # Match optional leading RPM directives then an absolute path
        m = re.match(r"^((?:%[^\s/]+\s+)*)(/\S.*)", entry)
        if m:
            return m.group(1) + normalize_abs_to_macro(m.group(2))
    return entry


def iter_file_lists(data: dict):
    """Yield every list from any `files:` key in the packages tree."""
    for pkg in data.get("packages", {}).values():
        if "files" in pkg:
            yield pkg["files"]
        if devel := pkg.get("devel"):
            if "files" in devel:
                yield devel["files"]


def collect_replacements(data: dict, reverse: bool) -> dict[str, str]:
    """Return a mapping of original entry -> normalized entry for changed entries."""
    replacements: dict[str, str] = {}
    for file_list in iter_file_lists(data):
        for entry in file_list or []:
            if entry is None:
                continue
            normalized = normalize_file_entry(entry, reverse)
            if normalized != entry:
                replacements[entry] = normalized
    return replacements


def apply_replacements(content: str, replacements: dict[str, str]) -> str:
    """Replace each old entry with the normalized form in the raw YAML text."""
    for old, new in replacements.items():
        # Quoted forms (most common in this file)
        content = content.replace(f'"{old}"', f'"{new}"')
        content = content.replace(f"'{old}'", f"'{new}'")
        # Unquoted list items:  "- /absolute/path"  or  "- %{_macro}/path"
        content = re.sub(
            r"(^\s*-\s+)" + re.escape(old) + r"(\s*)$",
            r"\g<1>" + new + r"\g<2>",
            content,
            flags=re.MULTILINE,
        )
    return content


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    reverse = "--reverse" in args

    repo_root = Path(__file__).resolve().parent.parent
    packages_yaml = repo_root / "packages.yaml"

    if not packages_yaml.exists():
        sys.exit(f"error: {packages_yaml} not found")

    content = packages_yaml.read_text()
    data = yaml.safe_load(content)

    replacements = collect_replacements(data, reverse)

    direction = "macros -> absolute" if reverse else "absolute -> macros"
    if not replacements:
        print(f"Nothing to normalize ({direction}) — no matching paths found.")
        return

    print(f"Direction: {direction}\n")
    for old, new in replacements.items():
        print(f"  {old!r}")
        print(f"    -> {new!r}")

    new_content = apply_replacements(content, replacements)

    if dry_run:
        print("\n[dry-run] No changes written.")
        return

    packages_yaml.write_text(new_content)
    print(f"\nUpdated {packages_yaml.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
