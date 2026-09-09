"""Tests for scripts/validate-packages.py (the pre-commit gate).

Since the lib.validation unification (docs/bugs.md, formerly BUG-0012),
scripts/validate-packages.py is a thin front-end over lib.validation -- the
same validator scripts/stage-validate.py's stage 0 runs. These tests only
cover main()'s *wiring*: does it call the right lib functions, does it exit
non-zero when any of them report errors, does it print warnings without
exiting. Each lib.validation function's own behavior has its own dedicated
tests in tests/test_validation_gaps.py and
tests/integration/test_validation_pipeline.py -- not duplicated here.
"""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

validate_packages = importlib.import_module("scripts.validate-packages")


def _minimal_package(**overrides):
    """A package dict that passes validate_package() cleanly by default."""
    pkg = {
        "version": "1.0",
        "license": "MIT",
        "summary": "Test package",
        "description": "A test package",
        "url": "https://github.com/org/a",
        "source": {"archives": ["https://github.com/org/a/archive/1.0.tar.gz"]},
        "build": {"system": "cmake"},
        "depends_on": [],
    }
    pkg.update(overrides)
    return pkg


@pytest.fixture
def stub_environment(monkeypatch, tmp_path):
    """Stub every global check main() runs besides per-package validate_package
    (group membership, duplicate urls, submodule url resolution, .gitmodules
    conventions) so a test can exercise real per-package validation without a
    real groups.yaml/.gitmodules on disk. Individual tests that care about one
    of these can un-stub it.
    """
    monkeypatch.setattr(
        validate_packages, "validate_group_membership", lambda pkgs: ([], [])
    )
    monkeypatch.setattr(
        validate_packages, "validate_no_duplicate_urls", lambda pkgs: ([], [])
    )
    monkeypatch.setattr(
        validate_packages,
        "validate_submodule_url_resolution",
        lambda pkgs, mods: ([], []),
    )
    monkeypatch.setattr(validate_packages, "validate_gitmodules", lambda: ([], []))
    # No .gitmodules on disk -> main()'s `GITMODULES.exists()` guard short-circuits
    # to an empty module list without needing a real file.
    monkeypatch.setattr(
        validate_packages, "GITMODULES", tmp_path / ".gitmodules-missing"
    )


def _set_packages(monkeypatch, packages):
    monkeypatch.setattr(validate_packages, "get_packages", lambda: packages)


class TestSelfDependency:
    """Self-dependency detection moved into lib.validation.validate_package
    (formerly only checked by this script) as part of the BUG-0012 unification."""

    def test_self_dependency_exits_nonzero(self, stub_environment, monkeypatch, capsys):
        _set_packages(monkeypatch, {"pkg-a": _minimal_package(depends_on=["pkg-a"])})

        with pytest.raises(SystemExit) as exc_info:
            validate_packages.main()

        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "pkg-a" in captured.err
        assert "self-dependency" in captured.err.lower()


class TestReleaseTypeValidation:
    """BUG-0014: an unknown auto_update.release_type must fail this gate,
    not silently pass through and later match no dispatch branch in
    update-versions.py.
    """

    def test_unknown_release_type_exits_nonzero(
        self, stub_environment, monkeypatch, capsys
    ):
        _set_packages(
            monkeypatch,
            {"pkg-a": _minimal_package(auto_update={"release_type": "latest-tagg"})},
        )

        with pytest.raises(SystemExit) as exc_info:
            validate_packages.main()

        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "pkg-a" in captured.err
        assert "latest-tagg" in captured.err

    def test_latest_tag_is_valid(self, stub_environment, monkeypatch, capsys):
        _set_packages(
            monkeypatch,
            {"pkg-a": _minimal_package(auto_update={"release_type": "latest-tag"})},
        )

        validate_packages.main()  # must not raise SystemExit

        captured = capsys.readouterr()
        assert "✓ packages.yaml validation passed" in captured.out


class TestFedoraOverrideValidation:
    """A single spec is now shared across every chroot (see docs/operations.md), so
    lib.yaml_utils.apply_os_overrides() only resolves `skip` from a `fedora:` block
    -- any other key is silently dropped by the build instead of applied. A
    per-version spec difference belongs in build.prep/commands/install as a literal
    `%if 0%{?fedora} == N ... %endif` conditional. This gate must catch a non-`skip`
    key before it can reappear (docs/bugs.md formerly BUG-0012: lib.validation used
    to accept `build`/`build_requires`/`requires` here even though this script
    rejected them -- stage-validate silently passed a block the build ignored).
    """

    def test_build_override_key_rejected(self, stub_environment, monkeypatch, capsys):
        _set_packages(
            monkeypatch,
            {
                "pkg-a": _minimal_package(
                    fedora={"43": {"build": {"prep": ["echo hi"]}}}
                )
            },
        )

        with pytest.raises(SystemExit) as exc_info:
            validate_packages.main()

        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "pkg-a" in captured.err
        assert "build" in captured.err
        assert "%if 0%{?fedora}" in captured.err

    def test_skip_key_is_valid(self, stub_environment, monkeypatch, capsys):
        _set_packages(
            monkeypatch, {"pkg-a": _minimal_package(fedora={"43": {"skip": True}})}
        )

        validate_packages.main()  # must not raise SystemExit

        captured = capsys.readouterr()
        assert "✓ packages.yaml validation passed" in captured.out

    def test_no_fedora_block_is_valid(self, stub_environment, monkeypatch, capsys):
        _set_packages(monkeypatch, {"pkg-a": _minimal_package()})

        validate_packages.main()  # must not raise SystemExit

        captured = capsys.readouterr()
        assert "✓ packages.yaml validation passed" in captured.out


class TestMainWiring:
    """Confirm main() surfaces global-check results correctly: errors from any
    lib.validation call block the commit (nonzero exit), warnings don't.
    """

    def test_global_error_exits_nonzero(self, stub_environment, monkeypatch, capsys):
        """A .gitmodules convention error (surfaced via validate_gitmodules,
        stubbed here to simulate one) must fail the gate the same way a
        per-package error does."""
        monkeypatch.setattr(
            validate_packages,
            "validate_gitmodules",
            lambda: (["submodule 'x' missing 'ignore = dirty'"], []),
        )
        _set_packages(monkeypatch, {"pkg-a": _minimal_package()})

        with pytest.raises(SystemExit) as exc_info:
            validate_packages.main()

        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "ignore = dirty" in captured.err

    def test_global_warning_does_not_exit(self, stub_environment, monkeypatch, capsys):
        """A duplicate-url warning (see validate_no_duplicate_urls) is printed
        but doesn't block the commit."""
        monkeypatch.setattr(
            validate_packages,
            "validate_no_duplicate_urls",
            lambda pkgs: ([], ["url 'https://x' is shared by packages: pkg-a, pkg-b"]),
        )
        _set_packages(monkeypatch, {"pkg-a": _minimal_package()})

        validate_packages.main()  # must not raise SystemExit

        captured = capsys.readouterr()
        assert "shared by packages" in captured.err
        assert "✓ packages.yaml validation passed" in captured.out

    def test_submodule_url_mismatch_warns_but_does_not_exit(
        self, stub_environment, monkeypatch, capsys
    ):
        """Real end-to-end wiring for the BUG-0013 url-mismatch check: main()
        passes GITMODULES's parsed modules through to
        validate_submodule_url_resolution (un-stubbed here) rather than
        swallowing them."""
        import lib.validation as lib_validation

        monkeypatch.setattr(
            validate_packages,
            "validate_submodule_url_resolution",
            lib_validation.validate_submodule_url_resolution,
        )
        gitmodules = validate_packages.GITMODULES.parent / ".gitmodules-real"
        gitmodules.write_text(
            '[submodule "submodules/org/a"]\n'
            "\tpath = submodules/org/a\n"
            "\turl = https://github.com/org/a.git\n"
        )
        monkeypatch.setattr(validate_packages, "GITMODULES", gitmodules)
        _set_packages(
            monkeypatch,
            {"pkg-a": _minimal_package(url="https://github.com/org/a")},
        )

        validate_packages.main()  # must not raise SystemExit

        captured = capsys.readouterr()
        assert "pkg-a" in captured.err
        assert "does not match any .gitmodules" in captured.err
        assert "✓ packages.yaml validation passed" in captured.out


class TestParity:
    """The point of the BUG-0012 unification: every lib.validation global check
    scripts/stage-validate.py runs must also be wired into this script's main(),
    so the two can never silently diverge again (one adding a check the other
    doesn't call). Spies on each lib function main() is documented to call and
    asserts every one actually fires exactly once per run.
    """

    def test_main_calls_every_global_check_exactly_once(
        self, stub_environment, monkeypatch
    ):
        calls: dict[str, int] = {}

        def _spy(name, result=([], [])):
            def _fn(*args, **kwargs):
                calls[name] = calls.get(name, 0) + 1
                return result

            return _fn

        monkeypatch.setattr(
            validate_packages,
            "validate_group_membership",
            _spy("validate_group_membership"),
        )
        monkeypatch.setattr(
            validate_packages,
            "validate_no_duplicate_urls",
            _spy("validate_no_duplicate_urls"),
        )
        monkeypatch.setattr(
            validate_packages,
            "validate_submodule_url_resolution",
            _spy("validate_submodule_url_resolution"),
        )
        monkeypatch.setattr(
            validate_packages, "validate_gitmodules", _spy("validate_gitmodules")
        )
        monkeypatch.setattr(
            validate_packages,
            "validate_package",
            _spy("validate_package", result=([], [])),
        )
        _set_packages(monkeypatch, {"pkg-a": _minimal_package()})

        validate_packages.main()

        assert calls == {
            "validate_package": 1,
            "validate_group_membership": 1,
            "validate_no_duplicate_urls": 1,
            "validate_submodule_url_resolution": 1,
            "validate_gitmodules": 1,
        }
