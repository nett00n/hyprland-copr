"""Unit tests for scripts/lib/log_analysis.py"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, Mock
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.log_analysis import (
    _analyze_srpm_log,
    _analyze_mock_log,
    _analyze_mock_build_log,
    _suggest_providers,
    _dnf_whatprovides,
    _dnf_search,
    _print_stage_issues,
    report_srpm_failures,
    report_mock_failures,
)


class TestAnalyzeSrpmLog:
    """Test SRPM stage log analysis."""

    def test_http_error_detection(self, tmp_path):
        """Detect HTTP download errors."""
        log_file = tmp_path / "10-srpm.log"
        log_file.write_text(
            "404 Client Error: Not Found for url: https://example.com/file.tar.gz\n"
        )
        issues = _analyze_srpm_log(log_file)
        assert len(issues) == 1
        assert "HTTP 404" in issues[0][2]
        assert "https://example.com/file.tar.gz" in issues[0][2]

    def test_missing_source_file_detection(self, tmp_path):
        """Detect missing source file after failed download."""
        log_file = tmp_path / "10-srpm.log"
        log_file.write_text(
            "error: Bad file: /root/rpmbuild/SOURCES/mpvpaper-1.2.1.tar.gz: No such file or directory\n"
        )
        issues = _analyze_srpm_log(log_file)
        assert len(issues) == 1
        assert "not downloaded" in issues[0][2]
        assert "mpvpaper-1.2.1.tar.gz" in issues[0][2]

    def test_multiple_http_errors(self, tmp_path):
        """Detect multiple HTTP errors in one log."""
        log_file = tmp_path / "10-srpm.log"
        log_file.write_text(
            "404 Client Error: Not Found for url: https://example.com/file1.tar.gz\n"
            "500 Client Error: Internal Server Error for url: https://example.com/file2.tar.gz\n"
        )
        issues = _analyze_srpm_log(log_file)
        assert len(issues) == 2
        assert issues[0][2].startswith("HTTP 404")
        assert issues[1][2].startswith("HTTP 500")

    def test_nonexistent_log_file(self, tmp_path):
        """Nonexistent log file returns empty list."""
        log_file = tmp_path / "nonexistent.log"
        issues = _analyze_srpm_log(log_file)
        assert issues == []

    def test_empty_log_file(self, tmp_path):
        """Empty log file returns empty list."""
        log_file = tmp_path / "10-srpm.log"
        log_file.write_text("")
        issues = _analyze_srpm_log(log_file)
        assert issues == []

    def test_log_without_errors(self, tmp_path):
        """Log without errors returns empty list."""
        log_file = tmp_path / "10-srpm.log"
        log_file.write_text("$ spectool -g -R /work/packages/test/test.spec\n")
        issues = _analyze_srpm_log(log_file)
        assert issues == []

    def test_missing_source_with_bz2(self, tmp_path):
        """Detect missing bz2 source file."""
        log_file = tmp_path / "10-srpm.log"
        log_file.write_text(
            "error: Bad file: /root/rpmbuild/SOURCES/archive-1.0.tar.bz2: No such file or directory\n"
        )
        issues = _analyze_srpm_log(log_file)
        assert len(issues) == 1
        assert "archive-1.0.tar.bz2" in issues[0][2]

    def test_missing_source_with_xz(self, tmp_path):
        """Detect missing xz source file."""
        log_file = tmp_path / "10-srpm.log"
        log_file.write_text(
            "error: Bad file: /root/rpmbuild/SOURCES/archive-1.0.tar.xz: No such file or directory\n"
        )
        issues = _analyze_srpm_log(log_file)
        assert len(issues) == 1
        assert "archive-1.0.tar.xz" in issues[0][2]

    def test_issue_tuple_structure(self, tmp_path):
        """Returned issue tuple has correct structure."""
        log_file = tmp_path / "10-srpm.log"
        log_file.write_text(
            "error: Bad file: /root/rpmbuild/SOURCES/test-1.0.tar.gz: No such file or directory\n"
        )
        issues = _analyze_srpm_log(log_file)
        assert len(issues) == 1
        lineno, raw_line, msg, dep, method = issues[0]
        assert isinstance(lineno, int)
        assert isinstance(raw_line, str)
        assert isinstance(msg, str)
        assert isinstance(dep, str)
        assert isinstance(method, str)
        assert method == "http"  # HTTP-related errors use 'http' method

    def test_generic_error_detection(self, tmp_path):
        """Detect generic error: lines."""
        log_file = tmp_path / "10-srpm.log"
        log_file.write_text("error: Something went wrong: details here\n")
        issues = _analyze_srpm_log(log_file)
        assert len(issues) == 1
        assert "SRPM error" in issues[0][2]
        assert "Something went wrong" in issues[0][2]

    def test_multiple_error_types(self, tmp_path):
        """Detect mix of different error types."""
        log_file = tmp_path / "10-srpm.log"
        log_file.write_text(
            "404 Client Error: Not Found for url: https://example.com/file.tar.gz\n"
            "error: Bad file: /root/rpmbuild/SOURCES/file.tar.gz: No such file or directory\n"
            "error: Permission denied: cannot read file\n"
        )
        issues = _analyze_srpm_log(log_file)
        assert len(issues) == 3
        assert "HTTP 404" in issues[0][2]
        assert "not downloaded" in issues[1][2]
        assert "Permission denied" in issues[2][2]


class TestAnalyzeMockLog:
    """Test mock orchestration log analysis."""

    def test_missing_builddep_detection(self, tmp_path):
        """Detect missing build dependency."""
        log_file = tmp_path / "20-mock.log"
        log_file.write_text("No match for argument: sndio-libs-devel\n")
        issues = _analyze_mock_log(log_file)
        assert len(issues) == 1
        assert "sndio-libs-devel" in issues[0][2]

    def test_package_conflict_detection(self, tmp_path):
        """Detect package conflicts."""
        log_file = tmp_path / "20-mock.log"
        log_file.write_text(
            "Problem: package pipewire-jack-audio-connection-kit-devel-1.4.10-1.fc43.x86_64 from updates conflicts with jack-audio-connection-kit-devel provided by jack-audio-connection-kit-devel-1.9.22-10.fc43.x86_64 from fedora\n"
        )
        issues = _analyze_mock_log(log_file)
        assert len(issues) == 1
        assert "conflicts" in issues[0][2]

    def test_nonexistent_mock_log(self, tmp_path):
        """Nonexistent log file returns empty list."""
        log_file = tmp_path / "20-mock.log"
        issues = _analyze_mock_log(log_file)
        assert issues == []


class TestAnalyzeMockBuildLog:
    """Test mock build log analysis."""

    def test_meson_dependency_error(self, tmp_path):
        """Detect meson missing dependency error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            'meson.build:86:14: ERROR: Dependency "upower-glib" not found, tried pkgconfig\n'
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "upower-glib" in issues[0][2]
        assert "pkgconfig" in issues[0][2]

    def test_meson_library_error(self, tmp_path):
        """Detect meson missing library error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "meson.build:98:20: ERROR: C++ shared or static library 'sndio' not found\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "sndio" in issues[0][2]

    def test_unexpanded_macro_error(self, tmp_path):
        """Detect unexpanded RPM macro."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text("+ %cmake\n")
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "unexpanded" in issues[0][2]
        assert "cmake" in issues[0][2]

    def test_missing_binary_error(self, tmp_path):
        """Detect missing binary error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "/var/tmp/rpm-tmp.PsPh8C: line 47: /usr/bin/cmake: No such file or directory\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "/usr/bin/cmake" in issues[0][2]

    def test_generic_build_error(self, tmp_path):
        """Detect build phase exit status error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "error: Bad exit status from /var/tmp/rpm-tmp.CA85tV (%build)\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "failed during build" in issues[0][2]
        assert "check previous lines" in issues[0][2]

    def test_nonexistent_mock_build_log(self, tmp_path):
        """Nonexistent log file returns empty list."""
        log_file = tmp_path / "21-mock-build.log"
        issues = _analyze_mock_build_log(log_file)
        assert issues == []

    def test_fg_no_job_control_error(self, tmp_path):
        """Detect fg: no job control error from unexpanded macro."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "/var/tmp/rpm-tmp.fzFQ77: line 47: fg: no job control\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "unexpanded" in issues[0][2]
        assert "cmake" in issues[0][2]

    def test_bare_command_not_found(self, tmp_path):
        """Detect command not found error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "/var/tmp/rpm-tmp.PsPh8C: line 47: cargo: command not found\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "cargo" in issues[0][2]
        assert "tool" in issues[0][4]

    def test_cmake_no_cmakelists(self, tmp_path):
        """Detect CMake error when CMakeLists.txt is missing."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            'CMake Error: The source directory "/builddir/build/src" does not appear to contain CMakeLists.txt\n'
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "wrong build_system" in issues[0][2]

    def test_cmake_missing_pkgconfig(self, tmp_path):
        """Detect CMake missing package configuration error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "CMake Error at CMakeLists.txt:128 (find_package):\n"
            '  Could not find a package configuration file provided by "glslang"\n'
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "glslang" in issues[0][2]
        assert "pkgconfig" in issues[0][4]

    def test_cmake_pkg_check_modules(self, tmp_path):
        """Detect CMake missing pkgconfig packages."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "CMake Error at /usr/share/cmake/Modules/FindPkgConfig.cmake:1093 (message):\n"
            "  The following required packages were not found:\n"
            "   - lcms2\n"
            "   - libpng\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "lcms2" in issues[0][2]
        assert "libpng" in issues[0][2]

    def test_cmake_missing_source_file(self, tmp_path):
        """Detect CMake missing source file error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "CMake Error at CMakeLists.txt:49 (add_library):\n"
            "  Cannot find source file:\n"
            "    cavacore.c\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "cavacore.c" in issues[0][2]

    def test_compiler_missing_header(self, tmp_path):
        """Detect compiler missing header error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "/path/to/file.cpp:11:10: fatal error: hyprland/src/managers/HookSystemManager.hpp: No such file or directory\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "HookSystemManager.hpp" in issues[0][2]

    def test_compiler_missing_internal_header(self, tmp_path):
        """Detect internal/private header not found."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "/path/to/plugin.cpp:5:10: fatal error: hyprland/src/internal/InternalHeader.hpp: No such file or directory\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "plugin may be incompatible" in issues[0][2]

    def test_make_missing_tool(self, tmp_path):
        """Detect make tool not found error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "make[1]: gcc: No such file or directory\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "gcc" in issues[0][2]

    def test_cp_missing_file(self, tmp_path):
        """Detect cp missing file error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "cp: cannot stat '/builddir/build/BUILD/test/README.md': No such file or directory\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "README.md" in issues[0][2]

    def test_meson_problem_error(self, tmp_path):
        """Detect meson problem encountered error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "meson.build:78:3: ERROR: Problem encountered: iniparser library is required\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "iniparser library is required" in issues[0][2]

    def test_meson_wrap_fallback(self, tmp_path):
        """Detect meson wrap fallback missing dependency."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "Looking for a fallback subproject for the dependency libcava\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "libcava" in issues[0][2]
        assert "pkgconfig" in issues[0][4]

    def test_unpackaged_files(self, tmp_path):
        """Detect unpackaged files error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "error: Installed (but unpackaged) file(s) found:\n"
            "/usr/lib/libtest.so\n"
        )
        issues = _analyze_mock_build_log(log_file)
        # Note: both line-by-line and multiline pass detect this (one for the error line, one for the block)
        assert any("unpackaged" in issue[2] for issue in issues)

    def test_cd_not_found(self, tmp_path):
        """Detect cd directory not found error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "/var/tmp/rpm-tmp.XXX: line 5: cd: wrong-dir-name: No such file or directory\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "wrong-dir-name" in issues[0][2]

    def test_empty_debugfiles(self, tmp_path):
        """Detect empty debugsourcefiles error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "error: Empty %files file /builddir/build/BUILD/test/debugsourcefiles.list\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "debugsourcefiles" in issues[0][2]

    def test_files_not_found(self, tmp_path):
        """Detect file not found in BUILDROOT error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "error: File not found: /builddir/build/BUILD/test/BUILDROOT/usr/lib/test.so\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "/usr/lib/test.so" in issues[0][2]

    def test_cargo_network_error(self, tmp_path):
        """Detect cargo network error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "error: failed to get `bitflags` as a dependency of package `cosmic-client-toolkit v0.2.0 (..)\n"
            "Caused by: [6] Could not resolve hostname (Could not resolve host: index.crates.io)\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "bitflags" in issues[0][2]

    def test_spec_file_macro(self, tmp_path):
        """Detect RPM macro not expanded in spec file."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            'error: File must begin with "/": %{_userunitdir}/app-graphical.slice\n'
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "_userunitdir" in issues[0][2]

    def test_cmake_missing_pkgconfig_by_name(self, tmp_path):
        """Detect CMake missing package by name."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "CMake Error at CMakeLists.txt:130 (find_package):\n"
            'By not providing "FindQt6.cmake" in CMAKE_MODULE_PATH\n'
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "Qt6" in issues[0][2]

    def test_multiple_cmake_packages_in_check_modules(self, tmp_path):
        """Detect multiple missing packages in cmake check modules."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "CMake Error at /usr/share/cmake/Modules/FindPkgConfig.cmake:1093 (message):\n"
            "  The following required packages were not found:\n"
            "   - lcms2\n"
            "   - libpng\n"
            "   - zlib\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "lcms2" in issues[0][2] and "libpng" in issues[0][2] and "zlib" in issues[0][2]

    def test_unpackaged_files_multiline_block(self, tmp_path):
        """Detect unpackaged files with multi-line block parsing."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "error: Installed (but unpackaged) file(s) found:\n"
            "/usr/lib/libtest.so\n"
            "/usr/lib/libtest.so.1\n"
            "/usr/include/test.h\n"
            "/usr/lib/pkgconfig/test.pc\n"
            "Child return code was: 1\n"
        )
        issues = _analyze_mock_build_log(log_file)
        # Both line-by-line and multiline block matches occur
        assert len(issues) >= 1
        # Check that the multiline block with categorization exists
        multiline_issue = [i for i in issues if "devel.files" in i[2]]
        assert len(multiline_issue) == 1
        assert "libtest.so" in multiline_issue[0][2]
        assert "test.h" in multiline_issue[0][2]
        assert "test.pc" in multiline_issue[0][2]

    def test_unpackaged_files_ignores_debug_files(self, tmp_path):
        """Unpackaged files block ignores debug files."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "error: Installed (but unpackaged) file(s) found:\n"
            "/usr/lib/libtest.so\n"
            "/usr/lib/debug/libtest.so.debug\n"
            "Child return code was: 1\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) >= 1
        # The multiline block should detect and list the non-debug file
        multiline_blocks = [i for i in issues if "installed but unpackaged" in i[2]]
        assert len(multiline_blocks) > 0
        # Should ignore .debug files
        assert ".debug" not in str(multiline_blocks[0][2])

    def test_unpackaged_files_separate_devel_and_main(self, tmp_path):
        """Unpackaged files block separates devel from main files."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "error: Installed (but unpackaged) file(s) found:\n"
            "/usr/lib/libtest.so\n"
            "/usr/include/test.h\n"
            "/usr/lib/pkgconfig/test.pc\n"
            "Child return code was: 1\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) >= 1
        multiline_issue = [i for i in issues if "devel.files" in i[2]]
        assert len(multiline_issue) > 0
        msg = multiline_issue[0][2]
        # Should mention both devel.files and files
        assert "devel.files" in msg
        assert "files:" in msg

    def test_compiler_error_undeclared_identifier(self, tmp_path):
        """Detect compiler error for undeclared identifier."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "/path/to/file.cpp:123:45: error: 'MyClass' was not declared in this scope\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "undeclared identifier" in issues[0][2]
        assert "line 123" in issues[0][2]

    def test_compiler_error_struct_member(self, tmp_path):
        """Detect compiler error for missing struct member."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "/path/to/file.c:456:10: error: 'struct Point' has no member named 'x'\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "struct/class has no such member" in issues[0][2]
        assert "API mismatch" in issues[0][2]

    def test_compiler_error_type_mismatch(self, tmp_path):
        """Detect compiler error for type mismatch."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "/path/to/file.cpp:789:5: error: expected 'int' but got 'double'\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "type mismatch" in issues[0][2]
        assert "API change" in issues[0][2]

    def test_linker_undefined_reference(self, tmp_path):
        """Detect linker undefined reference error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "/usr/bin/ld: /path/to/object.o: in function `main':\n"
            "(.text+0x123): undefined reference to `init_widget'\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "undefined reference" in issues[0][2]
        assert "init_widget" in issues[0][2]
        assert "missing library" in issues[0][2]

    def test_linker_undefined_symbol(self, tmp_path):
        """Detect linker undefined symbol error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "/usr/bin/ld: undefined reference to `my_function'\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "undefined reference" in issues[0][2]
        assert "my_function" in issues[0][2]

    def test_linker_return_code_failure(self, tmp_path):
        """Detect linker exit code failure."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "/usr/bin/g++ obj1.o obj2.o -o app\n"
            "collect2: error: ld returned 1 exit status\n"
        )
        issues = _analyze_mock_build_log(log_file)
        # Should detect the linker return code error
        linker_errors = [i for i in issues if "linker error" in i[2]]
        assert len(linker_errors) >= 1
        assert "linking failed" in linker_errors[0][2]

    def test_multiple_compiler_errors(self, tmp_path):
        """Detect multiple compiler errors in one log."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "/path/to/file.cpp:100:5: error: 'x' was not declared in this scope\n"
            "/path/to/file.cpp:200:10: error: expected 'int' but got 'char*'\n"
            "/path/to/file.cpp:300:15: error: 'MyFunc' has no member named 'value'\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 3
        assert all("compilation error" in i[2] for i in issues)

    def test_librpm_format_error(self, tmp_path):
        """Detect librpm format error for unknown tag."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "DEBUG util.py:461:  error: incorrect format: unknown tag: \"pkgid\"\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "librpm format error" in issues[0][2]
        assert "pkgid" in issues[0][2]

    def test_bad_exit_status_install_phase(self, tmp_path):
        """Detect RPM failure in %install phase."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "error: Bad exit status from /var/tmp/rpm-tmp.CA85tV (%install)\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "failed during installation" in issues[0][2]
        assert "check previous lines" in issues[0][2]

    def test_bad_exit_status_package_phase(self, tmp_path):
        """Detect RPM failure in %package phase."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "error: Bad exit status from /var/tmp/rpm-tmp.FGH123 (%package)\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "failed during packaging" in issues[0][2]

    def test_bad_exit_status_check_phase(self, tmp_path):
        """Detect RPM failure in %check phase."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "error: Bad exit status from /var/tmp/rpm-tmp.IJK456 (%check)\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "failed during test" in issues[0][2]

    def test_bad_exit_status_with_cmake_error_context(self, tmp_path):
        """Bad exit status includes error context extracted from previous lines."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "-- glaze dependency not found, retrieving v6.1.0\n"
            "CMake Error at /usr/share/cmake/Modules/ExternalProject/shared_internal_commands.cmake:928 (message):\n"
            "  error: could not find git for clone of glaze-populate\n"
            "-- Configuring incomplete, errors occurred!\n"
            "error: Bad exit status from /var/tmp/rpm-tmp.vmv3Hu (%build)\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) >= 1
        # Find the bad exit status issue
        bad_exit = [i for i in issues if "failed during" in i[2]]
        assert len(bad_exit) > 0
        # Should extract the actual error from previous lines
        assert "could not find git" in bad_exit[0][2]

    def test_bad_exit_status_with_generic_error_context(self, tmp_path):
        """Bad exit status includes generic error context."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "Processing some files...\n"
            "error: File not found: /some/path/file.so\n"
            "error: Bad exit status from /var/tmp/rpm-tmp.ABC123 (%install)\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) >= 1
        bad_exit = [i for i in issues if "failed during" in i[2]]
        assert len(bad_exit) > 0
        assert "File not found" in bad_exit[0][2]

    def test_bad_exit_status_with_missing_tool_context(self, tmp_path):
        """Bad exit status includes missing tool context."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "Building project...\n"
            "/var/tmp/rpm-tmp.XYZ789: line 42: git: command not found\n"
            "+ exit 1\n"
            "error: Bad exit status from /var/tmp/rpm-tmp.XYZ789 (%build)\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) >= 1
        bad_exit = [i for i in issues if "failed during" in i[2]]
        assert len(bad_exit) > 0
        # Should capture the "not found" error
        assert "not found" in bad_exit[0][2].lower() or "command" in bad_exit[0][2].lower()

    def test_patch_hunk_failed_single_file(self, tmp_path):
        """Detect patch hunk failure for single file."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "+ /usr/lib/rpm/rpmuncompress /builddir/build/SOURCES/fix-build.patch\n"
            "+ /usr/bin/patch -p1 -s --fuzz=0 --no-backup-if-mismatch -f\n"
            "1 out of 1 hunk FAILED -- saving rejects to file src/config/ConfigManager.cpp.rej\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "patch" in issues[0][2].lower()
        assert "fix-build.patch" in issues[0][2]
        assert "ConfigManager.cpp" in issues[0][2]

    def test_patch_hunk_failed_multiple_files(self, tmp_path):
        """Detect patch hunk failures for multiple files."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "+ /usr/lib/rpm/rpmuncompress /builddir/build/SOURCES/rawhide-fix.patch\n"
            "+ /usr/bin/patch -p1 -s --fuzz=0 --no-backup-if-mismatch -f\n"
            "1 out of 1 hunk FAILED -- saving rejects to file src/config/ConfigManager.cpp.rej\n"
            "1 out of 1 hunk FAILED -- saving rejects to file src/finders/desktop/DesktopFinder.cpp.rej\n"
        )
        issues = _analyze_mock_build_log(log_file)
        # Should detect both failures
        assert len(issues) >= 2
        assert any("ConfigManager.cpp" in i[2] for i in issues)
        assert any("DesktopFinder.cpp" in i[2] for i in issues)

    def test_patch_hunk_multiple_hunks_failed(self, tmp_path):
        """Detect patch with multiple hunks failed."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "+ /usr/lib/rpm/rpmuncompress /builddir/build/SOURCES/update.patch\n"
            "+ /usr/bin/patch -p1\n"
            "2 out of 3 hunks FAILED -- saving rejects to file file.c.rej\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) >= 1
        assert "file.c" in issues[0][2]

    def test_patch_hunk_failed_no_patch_name(self, tmp_path):
        """Detect patch failure even without finding patch filename."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "1 out of 1 hunk FAILED -- saving rejects to file some/path/file.cpp.rej\n"
        )
        issues = _analyze_mock_build_log(log_file)
        assert len(issues) == 1
        assert "file.cpp" in issues[0][2]
        assert "incompatible" in issues[0][2]

    def test_bad_exit_status_prep_with_patch_failure(self, tmp_path):
        """Bad exit status in prep phase includes patch failure context."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "+ /usr/lib/rpm/rpmuncompress /builddir/build/SOURCES/exclude-plugins.patch\n"
            "+ /usr/bin/patch -p1 -s --fuzz=0 --no-backup-if-mismatch -f\n"
            "1 out of 1 hunk FAILED -- saving rejects to file CMakeLists.txt.rej\n"
            "error: Bad exit status from /var/tmp/rpm-tmp.QRjhnW (%prep)\n"
        )
        issues = _analyze_mock_build_log(log_file)
        # Should have both the patch failure and the bad exit status issues
        assert len(issues) >= 2
        patch_issues = [i for i in issues if "patch failed to apply" in i[2]]
        assert len(patch_issues) > 0
        # Bad exit should reference the patch failure
        bad_exit = [i for i in issues if "failed during source preparation" in i[2]]
        assert len(bad_exit) > 0
        assert "patch failed" in bad_exit[0][2]

    def test_bad_exit_status_prep_with_no_file_to_patch(self, tmp_path):
        """Bad exit status in prep phase for 'No file to patch' error."""
        log_file = tmp_path / "21-mock-build.log"
        log_file.write_text(
            "+ /usr/lib/rpm/rpmuncompress /builddir/build/SOURCES/fix-build.patch\n"
            "+ /usr/bin/patch -p1 -s --fuzz=0 --no-backup-if-mismatch -f\n"
            "----- Patch 1 -----\n"
            "No file to patch.  Skipping patch.\n"
            "1 out of 1 hunk ignored\n"
            "error: Bad exit status from /var/tmp/rpm-tmp.FONkHT (%prep)\n"
        )
        issues = _analyze_mock_build_log(log_file)
        # Should detect the "No file to patch" context
        bad_exit = [i for i in issues if "failed during source preparation" in i[2]]
        assert len(bad_exit) > 0
        assert "No file to patch" in bad_exit[0][2]


class TestSuggestProviders:
    """Test the _suggest_providers function."""

    @patch("lib.log_analysis._dnf_whatprovides")
    def test_suggests_pkgconfig_method(self, mock_whatprovides):
        """Should call dnf whatprovides with pkgconfig() format."""
        mock_whatprovides.return_value = ["some-package"]
        result = _suggest_providers("openssl", "pkgconfig")
        mock_whatprovides.assert_called_with("pkgconfig(openssl)")
        assert result == ["some-package"]

    @patch("lib.log_analysis._dnf_whatprovides")
    def test_suggests_library_method(self, mock_whatprovides):
        """Should call dnf whatprovides with lib*.so format."""
        mock_whatprovides.return_value = ["libssl-devel"]
        result = _suggest_providers("ssl", "library")
        mock_whatprovides.assert_called_with("libssl.so*")
        assert result == ["libssl-devel"]

    @patch("lib.log_analysis._dnf_whatprovides")
    def test_suggests_builddep_method(self, mock_whatprovides):
        """Should try exact match first for builddep."""
        mock_whatprovides.return_value = ["missing-dep"]
        result = _suggest_providers("missing-dep", "builddep")
        mock_whatprovides.assert_called_with("missing-dep")
        assert result == ["missing-dep"]

    @patch("lib.log_analysis._dnf_search")
    @patch("lib.log_analysis._dnf_whatprovides")
    def test_suggests_builddep_fallback_to_search(self, mock_whatprovides, mock_search):
        """Should fallback to search when exact match fails for builddep."""
        mock_whatprovides.return_value = []
        mock_search.return_value = ["similar-dep"]
        result = _suggest_providers("missing-dep", "builddep")
        mock_search.assert_called_with("missing-dep")
        assert result == ["similar-dep"]

    @patch("lib.log_analysis._dnf_whatprovides")
    def test_suggests_rpm_macro_method(self, mock_whatprovides):
        """Should call dnf whatprovides with */macros format."""
        mock_whatprovides.return_value = ["cmake-rpm-macros"]
        result = _suggest_providers("cmake", "rpm_macro")
        mock_whatprovides.assert_called_with("*/macros.cmake")
        assert result == ["cmake-rpm-macros"]

    @patch("lib.log_analysis._dnf_whatprovides")
    def test_suggests_binary_method(self, mock_whatprovides):
        """Should call dnf whatprovides with full path for binary."""
        mock_whatprovides.return_value = ["cmake"]
        result = _suggest_providers("/usr/bin/cmake", "binary")
        mock_whatprovides.assert_called_with("/usr/bin/cmake")

    @patch("lib.log_analysis._dnf_whatprovides")
    def test_suggests_tool_method(self, mock_whatprovides):
        """Should call dnf whatprovides with */bin format for tool."""
        mock_whatprovides.return_value = ["gcc"]
        result = _suggest_providers("gcc", "tool")
        mock_whatprovides.assert_called_with("*/bin/gcc")

    @patch("lib.log_analysis._dnf_search")
    def test_suggests_search_method(self, mock_search):
        """Should call dnf search for search method."""
        mock_search.return_value = ["iniparser-dev"]
        result = _suggest_providers("iniparser", "search")
        mock_search.assert_called_with("iniparser")

    def test_suggests_unknown_method_returns_empty(self):
        """Should return empty list for unknown method."""
        result = _suggest_providers("anything", "unknown")
        assert result == []


class TestDnfWhatprovides:
    """Test the _dnf_whatprovides function."""

    @patch("subprocess.run")
    def test_whatprovides_returns_sorted_packages(self, mock_run):
        """Should return sorted unique package names."""
        mock_run.return_value = Mock(
            stdout="package1\npackage2\npackage1\npackage3\n",
            returncode=0,
        )
        result = _dnf_whatprovides("something")
        assert result == ["package1", "package2", "package3"]

    @patch("subprocess.run")
    def test_whatprovides_handles_exception(self, mock_run):
        """Should return empty list on exception."""
        mock_run.side_effect = Exception("Command failed")
        result = _dnf_whatprovides("something")
        assert result == []

    @patch("subprocess.run")
    def test_whatprovides_filters_empty_lines(self, mock_run):
        """Should filter out empty lines."""
        mock_run.return_value = Mock(
            stdout="package1\n\npackage2\n   \npackage3\n",
            returncode=0,
        )
        result = _dnf_whatprovides("something")
        assert result == ["package1", "package2", "package3"]


class TestDnfSearch:
    """Test the _dnf_search function."""

    @patch("subprocess.run")
    def test_search_strips_devel_suffix(self, mock_run):
        """Should strip -devel suffix from search."""
        mock_run.return_value = Mock(
            stdout="package\npackage-devel\n",
            returncode=0,
        )
        result = _dnf_search("package-devel")
        # Check that the call was made without -devel
        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        # The pattern should be 'package*' not 'package-devel*'
        # call_args is the command list like ["dnf", "repoquery", "package*", ...]
        assert any("package*" in str(arg) for arg in call_args)

    @patch("subprocess.run")
    def test_search_strips_libs_suffix(self, mock_run):
        """Should strip -libs suffix from search."""
        mock_run.return_value = Mock(
            stdout="package\n",
            returncode=0,
        )
        result = _dnf_search("package-libs")
        assert mock_run.called

    @patch("subprocess.run")
    def test_search_handles_exception(self, mock_run):
        """Should return empty list on exception."""
        mock_run.side_effect = Exception("Command failed")
        result = _dnf_search("something")
        assert result == []


class TestPrintStageIssues:
    """Test the _print_stage_issues function."""

    def test_prints_nothing_for_empty_issues(self, capsys):
        """Should not print anything when there are no issues."""
        first = [True]
        _print_stage_issues("test", "pkg", Path("/tmp/test.log"), [], first)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert first == [True]

    def test_prints_header_on_first_issue(self, capsys):
        """Should print header on first issue."""
        first = [True]
        issues = [(1, "error line", "error message", "dep", "method")]
        _print_stage_issues("test", "pkg", Path("/tmp/test.log"), issues, first)
        captured = capsys.readouterr()
        assert "Post-build analysis:" in captured.out
        assert first == [False]

    def test_prints_issue_details(self, capsys):
        """Should print issue details."""
        first = [True]
        issues = [(1, "error line", "error message", "dep", "method")]
        _print_stage_issues("test", "pkg", Path("/tmp/test.log"), issues, first)
        captured = capsys.readouterr()
        assert "error message" in captured.out
        assert "/tmp/test.log:1:" in captured.out
        assert "error line" in captured.out

    @patch("lib.log_analysis._suggest_providers")
    def test_prints_suggested_packages(self, mock_suggest, capsys):
        """Should print suggested packages when available."""
        mock_suggest.return_value = ["suggested-pkg"]
        first = [True]
        issues = [(1, "error line", "error message", "dep", "method")]
        _print_stage_issues("test", "pkg", Path("/tmp/test.log"), issues, first)
        captured = capsys.readouterr()
        assert "suggested-pkg" in captured.out

    def test_does_not_reprint_header_for_multiple_issues(self, capsys):
        """Should not reprint header for multiple issues."""
        first = [True]
        issues = [
            (1, "error 1", "msg 1", "dep1", "method1"),
            (2, "error 2", "msg 2", "dep2", "method2"),
        ]
        _print_stage_issues("test", "pkg", Path("/tmp/test.log"), issues, first)
        captured = capsys.readouterr()
        # Header should appear once
        assert captured.out.count("Post-build analysis:") == 1


class TestReportFailures:
    """Test report_srpm_failures and report_mock_failures functions."""

    def test_report_srpm_failures_iterates_packages(self, tmp_path, capsys):
        """Should process all packages."""
        packages = {"pkg1": {}, "pkg2": {}}
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "pkg1").mkdir()
        (log_dir / "pkg2").mkdir()
        (log_dir / "pkg1" / "10-srpm.log").write_text("")
        (log_dir / "pkg2" / "10-srpm.log").write_text("")

        report_srpm_failures(packages, log_dir)
        # Should complete without error

    def test_report_mock_failures_iterates_packages(self, tmp_path, capsys):
        """Should process all packages."""
        packages = {"pkg1": {}, "pkg2": {}}
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "pkg1").mkdir()
        (log_dir / "pkg2").mkdir()
        (log_dir / "pkg1" / "20-mock.log").write_text("")
        (log_dir / "pkg1" / "21-mock-build.log").write_text("")
        (log_dir / "pkg2" / "20-mock.log").write_text("")
        (log_dir / "pkg2" / "21-mock-build.log").write_text("")

        report_mock_failures(packages, log_dir)
        # Should complete without error
