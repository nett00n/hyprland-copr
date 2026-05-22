"""Tests for validate-package-urls.py script."""

import subprocess
import sys
from pathlib import Path
import shutil

import pytest


def run_validate_urls(
    tmp_path, packages_yaml_content: str, gitmodules_content: str
) -> tuple[int, str, str]:
    """Helper to run validate-package-urls.py in a temp directory.

    Creates a minimal repo structure with scripts/validate-package-urls.py
    and runs it so it finds packages.yaml and .gitmodules in the right place.

    Returns: (exit_code, stdout, stderr)
    """
    # Copy the validate-package-urls.py script to a scripts/ dir in tmp_path
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    original_script = Path(__file__).parent.parent / "scripts" / "validate-package-urls.py"
    shutil.copy(original_script, scripts_dir / "validate-package-urls.py")

    # Write files at repo root
    (tmp_path / "packages.yaml").write_text(packages_yaml_content)
    (tmp_path / ".gitmodules").write_text(gitmodules_content)

    # Run the script from within tmp_path
    script_path = scripts_dir / "validate-package-urls.py"

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    return result.returncode, result.stdout, result.stderr


class TestValidatePackageUrls:
    """Test validate-package-urls.py script."""

    def test_valid_https_urls(self, tmp_path):
        """Should accept valid https:// URLs."""
        packages_yaml = """test-pkg:
  url: https://github.com/example/test-pkg
"""
        gitmodules = """[submodule "submodules/example/test-pkg"]
\tpath = submodules/example/test-pkg
\turl = https://github.com/example/test-pkg
"""
        exit_code, stdout, stderr = run_validate_urls(tmp_path, packages_yaml, gitmodules)

        assert exit_code == 0
        assert "All package URLs match" in stdout

    def test_rejects_git_ssh_urls(self, tmp_path):
        """Should reject git@ SSH URLs."""
        packages_yaml = """test-pkg:
  url: git@github.com:example/test-pkg
"""
        gitmodules = """[submodule "submodules/example/test-pkg"]
\tpath = submodules/example/test-pkg
\turl = git@github.com:example/test-pkg
"""
        exit_code, stdout, stderr = run_validate_urls(tmp_path, packages_yaml, gitmodules)

        assert exit_code == 1
        assert "must be in https:// format" in stderr
        assert "git@" in stderr

    def test_detects_url_mismatch(self, tmp_path):
        """Should detect URLs that don't match between packages.yaml and .gitmodules."""
        packages_yaml = """test-pkg:
  url: https://github.com/example/test-pkg
"""
        gitmodules = """[submodule "submodules/example/test-pkg"]
\tpath = submodules/example/test-pkg
\turl = https://github.com/different/test-pkg
"""
        exit_code, stdout, stderr = run_validate_urls(tmp_path, packages_yaml, gitmodules)

        assert exit_code == 1
        assert "do not match" in stderr
        assert "https://github.com/example/test-pkg" in stderr
        assert "https://github.com/different/test-pkg" in stderr

    def test_multiple_packages_mixed_urls(self, tmp_path):
        """Should catch format errors before mismatch errors."""
        packages_yaml = """good-pkg:
  url: https://github.com/example/good-pkg
bad-pkg:
  url: git@github.com:example/bad-pkg
"""
        gitmodules = """[submodule "submodules/example/good-pkg"]
\tpath = submodules/example/good-pkg
\turl = https://github.com/example/good-pkg
[submodule "submodules/example/bad-pkg"]
\tpath = submodules/example/bad-pkg
\turl = git@github.com:example/bad-pkg
"""
        exit_code, stdout, stderr = run_validate_urls(tmp_path, packages_yaml, gitmodules)

        assert exit_code == 1
        # Format errors should be reported first
        assert "must be in https:// format" in stderr
        assert "bad-pkg" in stderr

    def test_http_urls_accepted(self, tmp_path):
        """Should accept http:// URLs (though https is preferred)."""
        packages_yaml = """test-pkg:
  url: http://example.com/test-pkg
"""
        gitmodules = """[submodule "submodules/example/test-pkg"]
\tpath = submodules/example/test-pkg
\turl = http://example.com/test-pkg
"""
        exit_code, stdout, stderr = run_validate_urls(tmp_path, packages_yaml, gitmodules)

        assert exit_code == 0
        assert "All package URLs match" in stdout

    def test_package_without_submodule(self, tmp_path):
        """Should handle packages without matching submodules."""
        packages_yaml = """test-pkg:
  url: https://github.com/example/test-pkg
"""
        gitmodules = ""  # No submodules

        exit_code, stdout, stderr = run_validate_urls(tmp_path, packages_yaml, gitmodules)

        # Should pass since there's no mismatch (no submodule to match against)
        assert exit_code == 0

    def test_cpptrace_case(self, tmp_path):
        """Should catch the cpptrace git@ URL case that prompted this feature."""
        packages_yaml = """cpptrace:
  version: 1.0.4
  url: git@github.com:jeremy-rifkin/cpptrace
"""
        gitmodules = """[submodule "submodules/jeremy-rifkin/cpptrace"]
\tpath = submodules/jeremy-rifkin/cpptrace
\turl = git@github.com:jeremy-rifkin/cpptrace
"""
        exit_code, stdout, stderr = run_validate_urls(tmp_path, packages_yaml, gitmodules)

        assert exit_code == 1
        assert "must be in https:// format" in stderr
        assert "cpptrace" in stderr
        assert "git@github.com" in stderr
