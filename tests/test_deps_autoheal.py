"""Tests for lib/deps_autoheal.py (#COPR-0029): resolve a missing build dependency
found in a mock log to a packages.yaml entry, apply it, and loop with a cycle cap."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from lib import deps_autoheal
from lib.deps_autoheal import (
    Fix,
    MissingDep,
    apply_fixes,
    autoheal_enabled,
    heal_loop,
    max_cycles,
    missing_build_deps,
    resolve_dep,
)

CMAKE_PKG_LOG = (
    "CMake Error at /usr/share/cmake/Modules/FindPkgConfig.cmake:1093 (message):\n"
    "  The following required packages were not found:\n"
    "\n"
    "   - hyprtoolkit>=0.6.0\n"
    "   - libcanberra\n"
)


def _log(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "21-mock-build.log"
    path.write_text(text)
    return path


def _write_packages(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


PACKAGES = """\
Hyprland:
  version: "0.57.0"
  build_requires:
    - cmake
    - hyprlang-devel
    - pkgconfig(zlib)
  depends_on:
    - hyprlang
hyprlang:
  version: "0.6.0"
  devel:
    files:
      - "%{_libdir}/pkgconfig/hyprlang.pc"
hyprtoolkit:
  version: "0.6.0"
  devel:
    files:
      - "%{_libdir}/pkgconfig/hyprtoolkit.pc"
app-only:
  version: "1.0"
no-depends:
  version: "1.0"
  build_requires:
    - cmake
"""


@pytest.fixture
def packages_yaml(tmp_path):
    return _write_packages(tmp_path / "packages.yaml", PACKAGES)


class TestMissingBuildDeps:
    def test_pkg_check_modules_yields_each_package_with_constraint_stripped(
        self, tmp_path
    ):
        deps = missing_build_deps(_log(tmp_path, CMAKE_PKG_LOG))
        assert deps == [
            MissingDep("hyprtoolkit", "pkgconfig", ">= 0.6.0"),
            MissingDep("libcanberra", "pkgconfig"),
        ]

    def test_constraint_is_read_from_the_package_list(self, tmp_path):
        log = _log(tmp_path, _dep_log("sdbus-c++>=2.0.0"))
        assert missing_build_deps(log) == [
            MissingDep("sdbus-c++", "pkgconfig", ">= 2.0.0")
        ]

    @pytest.mark.parametrize("op", [">=", "<=", "=", ">", "<"])
    def test_every_operator(self, tmp_path, op):
        log = _log(tmp_path, _dep_log(f"foo{op}1.2"))
        assert missing_build_deps(log) == [MissingDep("foo", "pkgconfig", f"{op} 1.2")]

    def test_cmake_config_package_is_cmake_method(self, tmp_path):
        log = _log(
            tmp_path,
            "CMake Error at CMakeLists.txt:128 (find_package):\n"
            '  Could not find a package configuration file provided by "glslang"\n',
        )
        assert missing_build_deps(log) == [MissingDep("glslang", "cmake")]

    def test_meson_pkgconfig_dependency(self, tmp_path):
        log = _log(
            tmp_path,
            'meson.build:86:14: ERROR: Dependency "upower-glib" not found, tried pkgconfig\n',
        )
        assert missing_build_deps(log) == [MissingDep("upower-glib", "pkgconfig")]

    def test_duplicates_collapse(self, tmp_path):
        log = _log(tmp_path, CMAKE_PKG_LOG + CMAKE_PKG_LOG)
        assert len(missing_build_deps(log)) == 2

    def test_html_escaped_constraint_is_stripped(self, tmp_path):
        log = _log(
            tmp_path,
            "CMake Error at /usr/share/cmake/Modules/FindPkgConfig.cmake:1 (message):\n"
            "  The following required packages were not found:\n"
            "   - hyprtoolkit&gt;=0.6.0\n",
        )
        assert missing_build_deps(log) == [
            MissingDep("hyprtoolkit", "pkgconfig", ">= 0.6.0")
        ]

    def test_other_failures_are_not_healable(self, tmp_path):
        log = _log(tmp_path, "/var/tmp/rpm-tmp.x: line 31: ninja: command not found\n")
        assert missing_build_deps(log) == []

    def test_missing_log(self, tmp_path):
        assert missing_build_deps(tmp_path / "nope.log") == []


class TestResolveDep:
    def test_fedora_provider_gives_pkgconfig_entry(self, packages_yaml):
        packages = yaml.safe_load(packages_yaml.read_text())
        with patch.object(
            deps_autoheal, "_whatprovides", return_value=["libcanberra-devel"]
        ) as wp:
            fix = resolve_dep(
                MissingDep("libcanberra", "pkgconfig"), "Hyprland", packages, "44"
            )
        assert fix == Fix(
            MissingDep("libcanberra", "pkgconfig"), "pkgconfig(libcanberra)", None
        )
        assert wp.call_args.args[0] == "pkgconfig(libcanberra)"
        assert wp.call_args.args[1] == "44"

    def test_cmake_dep_queries_cmake_provides(self, packages_yaml):
        packages = yaml.safe_load(packages_yaml.read_text())
        with patch.object(
            deps_autoheal, "_whatprovides", return_value=["glslang-devel"]
        ) as wp:
            fix = resolve_dep(MissingDep("glslang", "cmake"), "Hyprland", packages, "44")
        assert fix is not None and fix.build_requires == "cmake(glslang)"
        assert wp.call_args.args[0] == "cmake(glslang)"

    def test_constraint_is_kept_and_checked_against_the_provider(self, packages_yaml):
        packages = yaml.safe_load(packages_yaml.read_text())
        dep = MissingDep("sdbus-c++", "pkgconfig", ">= 2.0.0")
        with patch.object(
            deps_autoheal, "_whatprovides", return_value=["sdbus-cpp-devel"]
        ) as wp:
            fix = resolve_dep(dep, "Hyprland", packages, "44")
        assert fix == Fix(dep, "pkgconfig(sdbus-c++) >= 2.0.0", None)
        assert wp.call_args.args[0] == "pkgconfig(sdbus-c++) >= 2.0.0"

    def test_provider_too_old_means_no_fix(self, packages_yaml):
        packages = yaml.safe_load(packages_yaml.read_text())
        with patch.object(deps_autoheal, "_whatprovides", return_value=[]):
            assert (
                resolve_dep(
                    MissingDep("sdbus-c++", "pkgconfig", ">= 9"),
                    "Hyprland",
                    packages,
                    "43",
                )
                is None
            )

    def test_local_package_ignores_the_constraint(self, packages_yaml):
        packages = yaml.safe_load(packages_yaml.read_text())
        fix = resolve_dep(
            MissingDep("hyprtoolkit", "pkgconfig", ">= 0.6.0"),
            "Hyprland",
            packages,
            "44",
        )
        assert fix is not None and fix.build_requires == "hyprtoolkit-devel"

    def test_no_provider_means_no_fix(self, packages_yaml):
        packages = yaml.safe_load(packages_yaml.read_text())
        with patch.object(deps_autoheal, "_whatprovides", return_value=[]):
            assert (
                resolve_dep(MissingDep("nope", "pkgconfig"), "Hyprland", packages, "44")
                is None
            )

    def test_local_package_gives_devel_and_depends_on(self, packages_yaml):
        packages = yaml.safe_load(packages_yaml.read_text())
        with patch.object(deps_autoheal, "_whatprovides") as wp:
            fix = resolve_dep(
                MissingDep("hyprtoolkit", "pkgconfig"), "Hyprland", packages, "44"
            )
        assert fix == Fix(
            MissingDep("hyprtoolkit", "pkgconfig"), "hyprtoolkit-devel", "hyprtoolkit"
        )
        wp.assert_not_called()

    def test_local_match_is_case_insensitive(self, packages_yaml):
        packages = yaml.safe_load(packages_yaml.read_text())
        fix = resolve_dep(MissingDep("HyprToolkit", "cmake"), "Hyprland", packages, "44")
        assert fix is not None and fix.depends_on == "hyprtoolkit"

    def test_local_package_without_devel_falls_through_to_dnf(self, packages_yaml):
        """An app (no devel subpackage) provides no pkgconfig(); ask dnf instead."""
        packages = yaml.safe_load(packages_yaml.read_text())
        with patch.object(deps_autoheal, "_whatprovides", return_value=[]) as wp:
            fix = resolve_dep(
                MissingDep("app-only", "pkgconfig"), "Hyprland", packages, "44"
            )
        assert fix is None
        wp.assert_called_once()

    def test_package_never_depends_on_itself(self, packages_yaml):
        packages = yaml.safe_load(packages_yaml.read_text())
        with patch.object(deps_autoheal, "_whatprovides", return_value=[]):
            assert (
                resolve_dep(
                    MissingDep("hyprlang", "pkgconfig"), "hyprlang", packages, "44"
                )
                is None
            )


class TestApplyFixes:
    def test_adds_build_requires_sorted_and_depends_on(self, packages_yaml):
        added = apply_fixes(
            "Hyprland",
            [
                Fix(
                    MissingDep("hyprtoolkit", "pkgconfig"),
                    "hyprtoolkit-devel",
                    "hyprtoolkit",
                ),
                Fix(
                    MissingDep("libcanberra", "pkgconfig"),
                    "pkgconfig(libcanberra)",
                    None,
                ),
            ],
            path=packages_yaml,
        )
        assert added == ["hyprtoolkit-devel", "pkgconfig(libcanberra)"]
        data = yaml.safe_load(packages_yaml.read_text())
        assert data["Hyprland"]["build_requires"] == [
            "cmake",
            "hyprlang-devel",
            "hyprtoolkit-devel",
            "pkgconfig(libcanberra)",
            "pkgconfig(zlib)",
        ]
        assert data["Hyprland"]["depends_on"] == ["hyprlang", "hyprtoolkit"]

    def test_other_packages_untouched(self, packages_yaml):
        before = yaml.safe_load(packages_yaml.read_text())
        apply_fixes(
            "Hyprland",
            [Fix(MissingDep("x", "pkgconfig"), "pkgconfig(x)", None)],
            path=packages_yaml,
        )
        after = yaml.safe_load(packages_yaml.read_text())
        for name in ("hyprlang", "hyprtoolkit", "app-only", "no-depends"):
            assert after[name] == before[name]

    def test_constrained_entry_replaces_the_bare_one(self, packages_yaml):
        added = apply_fixes(
            "Hyprland",
            [
                Fix(
                    MissingDep("zlib", "pkgconfig", ">= 1.3"),
                    "pkgconfig(zlib) >= 1.3",
                    None,
                )
            ],
            path=packages_yaml,
        )
        assert added == ["pkgconfig(zlib) >= 1.3"]
        requires = yaml.safe_load(packages_yaml.read_text())["Hyprland"][
            "build_requires"
        ]
        assert "pkgconfig(zlib) >= 1.3" in requires
        assert "pkgconfig(zlib)" not in requires

    def test_existing_entry_is_not_added_twice(self, packages_yaml):
        added = apply_fixes(
            "Hyprland",
            [Fix(MissingDep("zlib", "pkgconfig"), "pkgconfig(zlib)", None)],
            path=packages_yaml,
        )
        assert added == []
        data = yaml.safe_load(packages_yaml.read_text())
        assert data["Hyprland"]["build_requires"].count("pkgconfig(zlib)") == 1

    def test_depends_on_is_not_created_when_absent(self, packages_yaml):
        """An absent depends_on means "infer from -devel names" (lib.deps); creating
        one holding only the new entry would drop every inferred dependency."""
        apply_fixes(
            "no-depends",
            [Fix(MissingDep("hyprtoolkit", "pkgconfig"), "hyprtoolkit-devel", "hyprtoolkit")],
            path=packages_yaml,
        )
        data = yaml.safe_load(packages_yaml.read_text())
        assert "depends_on" not in data["no-depends"]
        assert "hyprtoolkit-devel" in data["no-depends"]["build_requires"]

    def test_unknown_package_raises(self, packages_yaml):
        with pytest.raises(KeyError):
            apply_fixes(
                "ghost",
                [Fix(MissingDep("x", "pkgconfig"), "pkgconfig(x)", None)],
                path=packages_yaml,
            )


class TestSwitches:
    def test_default_on(self, monkeypatch):
        monkeypatch.delenv("AUTOHEAL", raising=False)
        assert autoheal_enabled() is True

    @pytest.mark.parametrize("value", ["false", "0", "no", "FALSE"])
    def test_off(self, monkeypatch, value):
        monkeypatch.setenv("AUTOHEAL", value)
        assert autoheal_enabled() is False

    @pytest.mark.parametrize("value", ["true", "1", "yes", ""])
    def test_on(self, monkeypatch, value):
        monkeypatch.setenv("AUTOHEAL", value)
        assert autoheal_enabled() is True

    def test_max_cycles_default_and_override(self, monkeypatch):
        monkeypatch.delenv("AUTOHEAL_MAX_CYCLES", raising=False)
        assert max_cycles() == 10
        monkeypatch.setenv("AUTOHEAL_MAX_CYCLES", "3")
        assert max_cycles() == 3
        monkeypatch.setenv("AUTOHEAL_MAX_CYCLES", "junk")
        assert max_cycles() == 10


def _dep_log(name: str) -> str:
    return (
        "CMake Error at /usr/share/cmake/Modules/FindPkgConfig.cmake:1 (message):\n"
        "  The following required packages were not found:\n"
        f"   - {name}\n"
    )


class TestHealLoop:
    def _run(self, tmp_path, packages_yaml, deps_by_cycle, limit=10):
        """Drive heal_loop with a fake rebuild: cycle N fails on deps_by_cycle[N]
        (None = the rebuild succeeds)."""
        log = tmp_path / "21-mock-build.log"
        log.write_text(_dep_log(deps_by_cycle[0]))
        calls = []

        def rebuild() -> bool:
            calls.append(1)
            nxt = deps_by_cycle[len(calls)] if len(calls) < len(deps_by_cycle) else None
            if nxt is None:
                return True
            log.write_text(_dep_log(nxt))
            return False

        with patch.object(deps_autoheal, "_whatprovides", return_value=["some-devel"]):
            result = heal_loop(
                "Hyprland",
                log_path=log,
                fedora_version="44",
                rebuild=rebuild,
                limit=limit,
                packages_path=packages_yaml,
                load_packages=lambda: yaml.safe_load(packages_yaml.read_text()),
            )
        return result, calls

    def test_heals_in_one_cycle(self, tmp_path, packages_yaml):
        result, calls = self._run(tmp_path, packages_yaml, ["libcanberra", None])
        assert result.ok is True
        assert result.cycles == 1 and len(calls) == 1
        assert result.changes == ["+pkgconfig(libcanberra)"]
        assert result.reason == "autoheal: +pkgconfig(libcanberra) (1 cycle)"

    def test_two_cycles_list_both_entries(self, tmp_path, packages_yaml):
        result, _ = self._run(tmp_path, packages_yaml, ["libcanberra", "libfoo", None])
        assert result.ok is True and result.cycles == 2
        assert result.reason == (
            "autoheal: +pkgconfig(libcanberra), +pkgconfig(libfoo) (2 cycles)"
        )

    def test_limit_exhausted_fails(self, tmp_path, packages_yaml):
        names = [f"lib{i}" for i in range(10)]
        result, calls = self._run(tmp_path, packages_yaml, names, limit=3)
        assert result.ok is False
        assert result.cycles == 3 and len(calls) == 3
        assert result.reason.startswith("autoheal: gave up after 3 cycles (+")
        data = yaml.safe_load(packages_yaml.read_text())
        assert "pkgconfig(lib0)" in data["Hyprland"]["build_requires"]

    def test_no_recognised_dep_does_nothing(self, tmp_path, packages_yaml):
        log = tmp_path / "21-mock-build.log"
        log.write_text("error: something else entirely\n")
        result = heal_loop(
            "Hyprland",
            log_path=log,
            fedora_version="44",
            rebuild=lambda: pytest.fail("must not rebuild"),
            limit=10,
            packages_path=packages_yaml,
            load_packages=lambda: yaml.safe_load(packages_yaml.read_text()),
        )
        assert result.ok is False and result.cycles == 0 and result.reason == ""

    def test_no_provider_does_nothing(self, tmp_path, packages_yaml):
        log = tmp_path / "21-mock-build.log"
        log.write_text(_dep_log("nonexistent"))
        with patch.object(deps_autoheal, "_whatprovides", return_value=[]):
            result = heal_loop(
                "Hyprland",
                log_path=log,
                fedora_version="44",
                rebuild=lambda: pytest.fail("must not rebuild"),
                limit=10,
                packages_path=packages_yaml,
                load_packages=lambda: yaml.safe_load(packages_yaml.read_text()),
            )
        assert result.ok is False and result.cycles == 0

    def test_dep_already_present_stops_loop(self, tmp_path, packages_yaml):
        """The edit did not help (mock still wants zlib): stop instead of spinning."""
        result, calls = self._run(tmp_path, packages_yaml, ["zlib"])
        assert result.ok is False and calls == []


# --- file lists in the same loop (#COPR-0029) ---------------------------------------

from lib.files_autoheal import FileEdit, pending_reason  # noqa: E402

T43, T44, T45 = "fedora-43-x86_64", "fedora-44-x86_64", "fedora-45-x86_64"
TARGETS = [T43, T44, T45]
COMPLETION = "%{_datadir}/bash-completion/completions/hyprctl"
BUILDROOT = "/builddir/build/BUILD/hyprland-0.57.0-build/BUILDROOT"
NOT_FOUND = f"error: File not found: {BUILDROOT}/usr/share/bash-completion/completions/hyprctl\n"
UNPACKAGED = (
    "error: Installed (but unpackaged) file(s) found:\n"
    "   /usr/lib64/systemd/user/hyprland-session.target\n"
    "Child return code was: 1\n"
)


@pytest.fixture
def files_yaml(tmp_path):
    path = tmp_path / "packages.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "Hyprland": {
                    "version": "0.57.0",
                    "build_requires": ["cmake"],
                    "files": ["%{_bindir}/hyprctl", COMPLETION],
                }
            }
        )
    )
    return path


def _vote_row(entry=COMPLETION):
    edit = FileEdit("-", "files", entry)
    return {
        "state": "failed",
        "version": "0.57.0-1.fc44",
        "reason": "autoheal: " + pending_reason([(edit, [T44])], 3),
    }


def _loop(tmp_path, files_yaml, log_text, *, rebuild=lambda: True, stages=None, limit=10):
    log = tmp_path / "21-mock-build.log"
    log.write_text(log_text)
    return heal_loop(
        "Hyprland",
        log_path=log,
        fedora_version="45",
        rebuild=rebuild,
        limit=limit,
        packages_path=files_yaml,
        load_packages=lambda: yaml.safe_load(files_yaml.read_text()),
        target=T45,
        version="0.57.0",
        targets=TARGETS,
        get_stage=lambda pkg, stage, t: (stages or {}).get(t),
    )


class TestHealLoopFiles:
    def test_unpackaged_file_is_added_and_rebuilt(self, tmp_path, files_yaml):
        result = _loop(tmp_path, files_yaml, UNPACKAGED)
        entry = "%{_libdir}/systemd/user/hyprland-session.target"
        assert result.ok and result.cycles == 1
        assert result.changes == [f"+files:{entry}"]
        assert result.reason == f"autoheal: +files:{entry} (1 cycle)"
        assert entry in yaml.safe_load(files_yaml.read_text())["Hyprland"]["files"]

    def test_unanimous_removal(self, tmp_path, files_yaml):
        stages = {T43: _vote_row(), T44: _vote_row()}
        result = _loop(tmp_path, files_yaml, NOT_FOUND, stages=stages)
        assert result.ok and result.reason == f"autoheal: -files:{COMPLETION} (1 cycle)"
        assert COMPLETION not in yaml.safe_load(files_yaml.read_text())["Hyprland"]["files"]

    def test_a_lone_vote_only_records_a_pending_reason(self, tmp_path, files_yaml):
        before = files_yaml.read_text()
        result = _loop(
            tmp_path,
            files_yaml,
            NOT_FOUND,
            rebuild=lambda: pytest.fail("a vote must not rebuild"),
        )
        assert not result.ok and result.cycles == 0 and result.changes == []
        assert result.reason == (
            f"autoheal: pending -files:{COMPLETION} "
            f"(needs all chroots; lacking on 1/3: {T45})"
        )
        assert files_yaml.read_text() == before

    def test_dependency_then_file_cycle(self, tmp_path, files_yaml):
        log = tmp_path / "21-mock-build.log"
        calls = []

        def rebuild():
            calls.append(1)
            if len(calls) == 1:
                log.write_text(UNPACKAGED)
                return False
            return True

        with patch.object(deps_autoheal, "_whatprovides", return_value=["x-devel"]):
            result = _loop(
                tmp_path, files_yaml, _dep_log("libcanberra"), rebuild=rebuild
            )
        assert result.ok and result.cycles == 2
        assert result.reason == (
            "autoheal: +pkgconfig(libcanberra), "
            "+files:%{_libdir}/systemd/user/hyprland-session.target (2 cycles)"
        )

    def test_gave_up_keeps_the_pending_votes(self, tmp_path, files_yaml):
        result = _loop(
            tmp_path, files_yaml, UNPACKAGED + NOT_FOUND, rebuild=lambda: False, limit=1
        )
        assert not result.ok and result.cycles == 1
        assert result.reason.startswith("autoheal: gave up after 1 cycle (+files:")
        assert f"; pending -files:{COMPLETION} (needs all chroots" in result.reason
