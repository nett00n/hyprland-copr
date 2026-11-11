"""RPM macro path normalization for packages.yaml."""

import re

# Ordered longest-first so more-specific prefixes win when going abs -> macro.
PREFIXES: list[tuple[str, str]] = [
    ("/usr/lib/systemd/system", "%{_unitdir}"),
    ("/usr/lib/systemd/user", "%{_userunitdir}"),
    ("/usr/lib/sysusers.d", "%{_sysusersdir}"),
    ("/usr/lib/tmpfiles.d", "%{_tmpfilesdir}"),
    # #BUG-0047: explicit so /usr/lib/x <-> %{_prefix}/lib/x is symmetric (there is
    # no dedicated macro for /usr/lib; /usr/lib64 is %{_libdir}).
    ("/usr/lib", "%{_prefix}/lib"),
    ("/usr/share/doc", "%{_docdir}"),
    ("/usr/share/info", "%{_infodir}"),
    ("/usr/share/man", "%{_mandir}"),
    ("/usr/include", "%{_includedir}"),
    ("/usr/libexec", "%{_libexecdir}"),
    ("/usr/share", "%{_datadir}"),
    ("/usr/lib64", "%{_libdir}"),
    ("/var/lib", "%{_sharedstatedir}"),
    ("/usr/bin", "%{_bindir}"),
    ("/usr/sbin", "%{_sbindir}"),
    ("/etc", "%{_sysconfdir}"),
    ("/usr", "%{_prefix}"),
    ("/run", "%{_rundir}"),
    ("/var", "%{_localstatedir}"),
]


def normalize_abs_to_macro(path: str) -> str:
    """Replace an absolute path prefix with the most specific RPM macro."""
    for prefix, macro in PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return macro + path[len(prefix) :]
    return path


def normalize_macro_to_abs(path: str) -> str:
    """Replace a leading RPM macro with its absolute path equivalent."""
    for prefix, macro in PREFIXES:
        macro_slash = macro + "/"
        if path == macro:
            return prefix
        if path.startswith(macro_slash):
            return prefix + path[len(macro) :]
    return path


# #BUG-0047
def normalize_file_entry(entry: str, reverse: bool) -> str:
    """Normalize a file entry, handling leading RPM directives.

    Forward (default):  /usr/bin/foo         -> %{_bindir}/foo
    Reverse:            %{_bindir}/foo        -> /usr/bin/foo
    Unchanged:          %license LICENSE      -> %license LICENSE
    """
    if reverse:
        m = re.match(r"^((?:%[^\s{][^\s]*\s+)*)(%\{[^}]+\}.*)", entry)
        if m:
            return m.group(1) + normalize_macro_to_abs(m.group(2))
    else:
        m = re.match(r"^((?:%[^\s/]+\s+)*)(/\S.*)", entry)
        if m:
            return m.group(1) + normalize_abs_to_macro(m.group(2))
        # #BUG-0047: already macro form but non-canonical (e.g. %{_prefix}/bin/x):
        # round-trip through the absolute path so it lands on the canonical macro.
        m = re.match(r"^((?:%[^\s{][^\s]*\s+)*)(%\{[^}]+\}.*)", entry)
        if m:
            as_abs = normalize_macro_to_abs(m.group(2))
            if as_abs.startswith("/"):
                return m.group(1) + normalize_abs_to_macro(as_abs)
    return entry
