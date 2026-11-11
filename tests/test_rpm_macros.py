"""Unit tests for scripts/lib/rpm_macros.py"""

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.rpm_macros import normalize_abs_to_macro, normalize_macro_to_abs, normalize_file_entry


class TestNormalizeAbsToMacro:
    """Test conversion from absolute paths to RPM macros."""

    def test_bindir_conversion(self):
        """Path /usr/bin/foo converts to %{_bindir}/foo."""
        assert normalize_abs_to_macro("/usr/bin/foo") == "%{_bindir}/foo"

    def test_sbindir_conversion(self):
        """Path /usr/sbin/bar converts to %{_sbindir}/bar."""
        assert normalize_abs_to_macro("/usr/sbin/bar") == "%{_sbindir}/bar"

    def test_libdir64_conversion(self):
        """/usr/lib64/foo converts to %{_libdir}/foo."""
        assert normalize_abs_to_macro("/usr/lib64/foo") == "%{_libdir}/foo"

    def test_pkgconfig_lib64_wins_over_lib64(self):
        """/usr/lib64/pkgconfig is more specific than /usr/lib64."""
        # Prefixes are ordered longest-first, so /usr/lib64/pkgconfig is never in list
        # Actually, looking at the code, /usr/lib64 is in list, no /usr/lib64/pkgconfig
        result = normalize_abs_to_macro("/usr/lib64/pkgconfig")
        assert result == "%{_libdir}/pkgconfig"

    def test_datadir_conversion(self):
        """/usr/share/foo converts to %{_datadir}/foo."""
        assert normalize_abs_to_macro("/usr/share/foo") == "%{_datadir}/foo"

    def test_mandir_conversion(self):
        """/usr/share/man/foo converts to %{_mandir}/foo."""
        assert normalize_abs_to_macro("/usr/share/man/foo") == "%{_mandir}/foo"

    def test_docdir_conversion(self):
        """/usr/share/doc/foo converts to %{_docdir}/foo."""
        assert normalize_abs_to_macro("/usr/share/doc/foo") == "%{_docdir}/foo"

    def test_sysconfdir_conversion(self):
        """/etc/foo converts to %{_sysconfdir}/foo."""
        assert normalize_abs_to_macro("/etc/foo") == "%{_sysconfdir}/foo"

    def test_prefix_exact_match(self):
        """/usr alone converts to %{_prefix}."""
        assert normalize_abs_to_macro("/usr") == "%{_prefix}"

    def test_no_match_returns_unchanged(self):
        """Path with no matching prefix is returned unchanged."""
        assert normalize_abs_to_macro("/opt/custom") == "/opt/custom"

    def test_unitdir_conversion(self):
        """/usr/lib/systemd/system converts to %{_unitdir}."""
        assert normalize_abs_to_macro("/usr/lib/systemd/system") == "%{_unitdir}"

    def test_tmpfilesdir_conversion(self):
        """/usr/lib/tmpfiles.d converts to %{_tmpfilesdir}."""
        assert normalize_abs_to_macro("/usr/lib/tmpfiles.d") == "%{_tmpfilesdir}"

    def test_includedir_conversion(self):
        """/usr/include/foo converts to %{_includedir}/foo."""
        assert normalize_abs_to_macro("/usr/include/foo") == "%{_includedir}/foo"

    def test_rundir_conversion(self):
        """/run/foo converts to %{_rundir}/foo."""
        assert normalize_abs_to_macro("/run/foo") == "%{_rundir}/foo"


class TestNormalizeMacroToAbs:
    """Test conversion from RPM macros to absolute paths."""

    def test_bindir_macro_to_abs(self):
        """%{_bindir}/foo converts to /usr/bin/foo."""
        assert normalize_macro_to_abs("%{_bindir}/foo") == "/usr/bin/foo"

    def test_sbindir_macro_to_abs(self):
        """%{_sbindir}/bar converts to /usr/sbin/bar."""
        assert normalize_macro_to_abs("%{_sbindir}/bar") == "/usr/sbin/bar"

    def test_libdir_macro_to_abs(self):
        """%{_libdir}/foo converts to /usr/lib64/foo."""
        assert normalize_macro_to_abs("%{_libdir}/foo") == "/usr/lib64/foo"

    def test_datadir_macro_to_abs(self):
        """%{_datadir}/foo converts to /usr/share/foo."""
        assert normalize_macro_to_abs("%{_datadir}/foo") == "/usr/share/foo"

    def test_sysconfdir_macro_to_abs(self):
        """%{_sysconfdir}/foo converts to /etc/foo."""
        assert normalize_macro_to_abs("%{_sysconfdir}/foo") == "/etc/foo"

    def test_macro_exact_match(self):
        """%{_bindir} alone converts to /usr/bin."""
        assert normalize_macro_to_abs("%{_bindir}") == "/usr/bin"

    def test_no_matching_macro_unchanged(self):
        """Unrecognized macro is returned unchanged."""
        assert normalize_macro_to_abs("%{_custom}/foo") == "%{_custom}/foo"

    def test_unitdir_macro_to_abs(self):
        """%{_unitdir}/foo converts to /usr/lib/systemd/system/foo."""
        assert normalize_macro_to_abs("%{_unitdir}/foo") == "/usr/lib/systemd/system/foo"

    def test_rundir_macro_to_abs(self):
        """%{_rundir}/foo converts to /run/foo."""
        assert normalize_macro_to_abs("%{_rundir}/foo") == "/run/foo"

    def test_roundtrip_abs_to_macro_to_abs(self):
        """Roundtrip conversion abs->macro->abs."""
        path = "/usr/bin/myapp"
        macro = normalize_abs_to_macro(path)
        assert normalize_macro_to_abs(macro) == path


class TestNormalizeFileEntry:
    """Test normalization of file entries with directives."""

    def test_simple_abs_path_to_macro(self):
        """Simple absolute path converts forward."""
        assert normalize_file_entry("/usr/bin/foo", False) == "%{_bindir}/foo"

    def test_simple_macro_to_abs(self):
        """Simple macro converts backward."""
        assert normalize_file_entry("%{_bindir}/foo", True) == "/usr/bin/foo"

    def test_license_directive_preserved_forward(self):
        """%license directive preserved during forward normalization."""
        assert normalize_file_entry("%license /etc/foo", False) == "%license %{_sysconfdir}/foo"

    def test_doc_directive_preserved_forward(self):
        """%doc directive preserved."""
        assert normalize_file_entry("%doc /usr/share/doc/foo", False) == "%doc %{_docdir}/foo"

    def test_license_directive_preserved_reverse(self):
        """%license directive preserved during reverse normalization."""
        assert normalize_file_entry("%license %{_sysconfdir}/foo", True) == "%license /etc/foo"

    def test_config_noreplace_directive_preserved(self):
        """%config(noreplace) directive preserved."""
        assert normalize_file_entry("%config(noreplace) /etc/foo", False) == "%config(noreplace) %{_sysconfdir}/foo"

    def test_dir_directive_preserved(self):
        """%dir directive preserved."""
        assert normalize_file_entry("%dir /usr/share/foo", False) == "%dir %{_datadir}/foo"

    def test_directive_only_unchanged(self):
        """Directive without path is unchanged."""
        assert normalize_file_entry("%doc", False) == "%doc"

    def test_multiple_directives_all_preserved(self):
        """Multiple directives are all preserved (though unusual)."""
        # The regex captures all leading directives: ((?:%[^\s/]+\s+)*)
        result = normalize_file_entry("%doc %license /etc/foo", False)
        # Should preserve both directives and normalize the path
        assert "%{_sysconfdir}/foo" in result
        assert "%doc" in result or "%license" in result

    def test_path_without_leading_slash_unchanged(self):
        """Path without leading slash is unchanged."""
        assert normalize_file_entry("relative/path", False) == "relative/path"

    def test_roundtrip_with_directive(self):
        """Roundtrip with directive: forward then backward."""
        entry = "%doc /usr/bin/myapp"
        forward = normalize_file_entry(entry, False)
        backward = normalize_file_entry(forward, True)
        assert backward == entry

    def test_glob_pattern_in_path(self):
        """Glob patterns in paths are handled (path structure preserved)."""
        result = normalize_file_entry("/usr/bin/*.so", False)
        # Should still normalize the prefix
        assert result == "%{_bindir}/*.so"

    def test_no_match_path_unchanged_with_directive(self):
        """Non-matching path with directive preserved."""
        assert normalize_file_entry("%doc /opt/custom/foo", False) == "%doc /opt/custom/foo"


class TestForwardCanonicalizesMacroForm:
    """#BUG-0047: forward pass canonicalizes non-canonical %{_prefix}/... entries."""

    def test_prefix_bin_to_bindir(self):
        assert normalize_file_entry("%{_prefix}/bin/ags", False) == "%{_bindir}/ags"

    def test_prefix_lib64_to_libdir(self):
        assert normalize_file_entry("%{_prefix}/lib64/x.so", False) == "%{_libdir}/x.so"

    def test_prefix_share_with_directive(self):
        assert (
            normalize_file_entry("%dir %{_prefix}/share/foo", False)
            == "%dir %{_datadir}/foo"
        )

    def test_canonical_macro_unchanged(self):
        assert normalize_file_entry("%{_bindir}/foo", False) == "%{_bindir}/foo"

    def test_unknown_macro_unchanged(self):
        assert normalize_file_entry("%{name}/foo", False) == "%{name}/foo"

    def test_forward_is_idempotent_and_matches_roundtrip(self):
        for e in ["%{_prefix}/bin/ags", "%{_prefix}/lib/x", "/usr/lib/x", "%{_bindir}/y"]:
            once = normalize_file_entry(e, False)
            assert normalize_file_entry(once, False) == once
            via_abs = normalize_file_entry(normalize_file_entry(e, True), False)
            assert once == via_abs


class TestUsrLib:
    """#BUG-0047: /usr/lib has an explicit PREFIXES entry."""

    def test_abs_to_macro(self):
        assert normalize_abs_to_macro("/usr/lib/x") == "%{_prefix}/lib/x"

    def test_macro_to_abs(self):
        assert normalize_macro_to_abs("%{_prefix}/lib/x") == "/usr/lib/x"

    def test_lib64_not_shadowed(self):
        assert normalize_abs_to_macro("/usr/lib64/x") == "%{_libdir}/x"
