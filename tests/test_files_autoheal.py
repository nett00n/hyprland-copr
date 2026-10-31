"""Tests for lib/files_autoheal.py (#COPR-0029): heal the files:/devel.files: lists
from rpmbuild's `File not found` / `unpackaged` errors, removals only by union."""

from pathlib import Path

import pytest
import yaml

from lib.files_autoheal import (
    FileEdit,
    apply_edits,
    classify,
    entry_path,
    owners,
    parse_pending,
    pending_reason,
    plan,
    to_entry,
)

BUILDROOT = "/builddir/build/BUILD/hyprland-0.57.0-build/BUILDROOT"
T43, T44, T45 = "fedora-43-x86_64", "fedora-44-x86_64", "fedora-45-x86_64"
TARGETS = [T43, T44, T45]
COMPLETION = "%{_datadir}/bash-completion/completions/hyprctl"

META = {
    "version": "0.57.0",
    "files": [
        "%doc README.md",
        "%license LICENSE",
        "%{_bindir}/hyprctl",
        COMPLETION,
        "%{_datadir}/hypr/",
        "%{_datadir}/wayland-sessions/hyprland*.desktop",
        "%{_prefix}/bin/Hyprland",
    ],
    "devel": {
        "files": [
            "%{_includedir}/hyprland/",
            "%{_prefix}/share/pkgconfig/hyprland.pc",
        ]
    },
}


def _log(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "21-mock-build.log"
    path.write_text(text)
    return path


def _not_found(tmp_path: Path, *paths: str) -> Path:
    body = "".join(f"error: File not found: {BUILDROOT}{p}\n" for p in paths)
    return _log(tmp_path, "Processing files: hyprland-0.57.0-2.fc45\n" + body)


class TestEntryPath:
    @pytest.mark.parametrize(
        "entry, expected",
        [
            ("%{_bindir}/hyprctl", "/usr/bin/hyprctl"),
            ("%{_prefix}/bin/Hyprland", "/usr/bin/Hyprland"),
            ("%config(noreplace) %{_sysconfdir}/foo.conf", "/etc/foo.conf"),
            ("%dir %{_datadir}/hypr", "/usr/share/hypr"),
            ("%{_datadir}/%{name}/x", "/usr/share/pkg/x"),
            ("%{_datadir}/%{name}-%{version}/x", "/usr/share/pkg-0.57.0/x"),
            (
                "%{bash_completions_dir}/hyprctl",
                "/usr/share/bash-completion/completions/hyprctl",
            ),
            (
                "%{fish_completions_dir}/x.fish",
                "/usr/share/fish/vendor_completions.d/x.fish",
            ),
            ("%{zsh_completions_dir}/_x", "/usr/share/zsh/site-functions/_x"),
            ("%{_libdir}/libx.so*", "/usr/lib64/libx.so*"),
            ("%{_datadir}/hypr/", "/usr/share/hypr/"),
        ],
    )
    def test_expands(self, entry, expected):
        assert entry_path(entry, META, "pkg") == expected

    @pytest.mark.parametrize(
        "entry", ["%doc README.md", "%license LICENSE", "%{python3_sitelib}/foo"]
    )
    def test_not_a_buildroot_path(self, entry):
        """%doc/%license live under BUILD, and an unknown macro cannot be matched."""
        assert entry_path(entry, META, "pkg") is None


class TestOwners:
    def test_exact(self):
        assert owners("/usr/share/bash-completion/completions/hyprctl", META, "H") == [
            ("files", COMPLETION)
        ]

    def test_glob_entry_covers_a_concrete_path(self):
        assert owners("/usr/share/wayland-sessions/hyprland.desktop", META, "H") == [
            ("files", "%{_datadir}/wayland-sessions/hyprland*.desktop")
        ]

    def test_glob_path_from_the_log_matches_its_own_entry(self):
        assert owners("/usr/share/wayland-sessions/hyprland*.desktop", META, "H") == [
            ("files", "%{_datadir}/wayland-sessions/hyprland*.desktop")
        ]

    def test_directory_entry_covers_children_and_itself(self):
        entry = ("files", "%{_datadir}/hypr/")
        assert owners("/usr/share/hypr/hyprland.conf", META, "H") == [entry]
        assert owners("/usr/share/hypr", META, "H") == [entry]

    def test_devel_list(self):
        assert owners("/usr/include/hyprland/api.h", META, "H") == [
            ("devel.files", "%{_includedir}/hyprland/")
        ]

    def test_unrelated(self):
        assert owners("/usr/share/other/x", META, "H") == []


class TestClassifyAndEntry:
    @pytest.mark.parametrize(
        "path",
        [
            "/usr/include/x/y.h",
            "/usr/lib64/pkgconfig/x.pc",
            "/usr/share/pkgconfig/x.pc",
            "/usr/lib64/cmake/x/xConfig.cmake",
            "/usr/lib64/libx.a",
        ],
    )
    def test_devel(self, path):
        assert classify(path) == "devel.files"

    @pytest.mark.parametrize(
        "path", ["/usr/bin/x", "/usr/lib64/libx.so", "/usr/share/x/y.conf"]
    )
    def test_main(self, path):
        assert classify(path) == "files"

    def test_to_entry_uses_macros(self):
        assert (
            to_entry("/usr/lib64/systemd/user/x.target")
            == "%{_libdir}/systemd/user/x.target"
        )
        assert to_entry("/usr/lib/foo") == "%{_prefix}/lib/foo"
        assert to_entry("/usr/bin/foo") == "%{_bindir}/foo"


class TestPendingReason:
    def test_format_and_round_trip(self):
        edit = FileEdit("-", "files", "%{_bindir}/x")
        text = pending_reason([(edit, [T45])], 3)
        assert text == (
            "pending -files:%{_bindir}/x (needs all chroots; lacking on 1/3: "
            f"{T45})"
        )
        assert parse_pending(f"autoheal: {text}") == {"files:%{_bindir}/x"}

    def test_several_entries(self):
        a = FileEdit("-", "files", "%{_bindir}/a")
        b = FileEdit("-", "devel.files", "%{_includedir}/b/")
        reason = "autoheal: " + pending_reason([(a, [T44, T45]), (b, [T45])], 3)
        assert parse_pending(reason) == {
            "files:%{_bindir}/a",
            "devel.files:%{_includedir}/b/",
        }
        assert "lacking on 1/3: " + T45 in reason  # the least-agreed entry

    def test_other_reasons_have_no_votes(self):
        assert parse_pending("autoheal: +pkgconfig(x) (1 cycle)") == set()
        assert parse_pending("") == set()
        assert parse_pending(None) == set()


def _vote(entry: str, version: str = "0.57.0-1.fc44", state: str = "failed") -> dict:
    edit = FileEdit("-", "files", entry)
    return {
        "state": state,
        "version": version,
        "reason": "autoheal: " + pending_reason([(edit, [T44])], 3),
    }


def _plan(tmp_path, stages, target=T45, targets=TARGETS, meta=META, paths=None):
    log = _not_found(tmp_path, *(paths or ["/usr/share/bash-completion/completions/hyprctl"]))
    return plan(
        "Hyprland",
        meta,
        log,
        target=target,
        version="0.57.0",
        targets=targets,
        get_stage=lambda pkg, stage, t: stages.get(t),
    )


class TestPlanRemovals:
    def test_unanimous_vote_removes(self, tmp_path):
        stages = {T43: _vote(COMPLETION), T44: _vote(COMPLETION)}
        result = _plan(tmp_path, stages)
        assert result.edits == [FileEdit("-", "files", COMPLETION)]
        assert result.pending == []

    def test_a_chroot_without_a_vote_blocks_the_removal(self, tmp_path):
        stages = {T43: _vote(COMPLETION)}  # fedora-44 has no row: not run / passed
        result = _plan(tmp_path, stages)
        assert result.edits == []
        assert result.pending == [(FileEdit("-", "files", COMPLETION), [T43, T45])]

    def test_a_chroot_that_builds_withdraws_its_vote(self, tmp_path):
        stages = {T43: _vote(COMPLETION), T44: _vote(COMPLETION, state="success")}
        assert _plan(tmp_path, stages).edits == []

    def test_a_vote_for_an_old_version_does_not_count(self, tmp_path):
        stages = {T43: _vote(COMPLETION), T44: _vote(COMPLETION, version="0.56.0-1.fc44")}
        assert _plan(tmp_path, stages).edits == []

    def test_a_vote_for_another_entry_does_not_count(self, tmp_path):
        stages = {T43: _vote(COMPLETION), T44: _vote("%{_bindir}/hyprctl")}
        assert _plan(tmp_path, stages).edits == []

    def test_unknown_current_target_is_never_unanimous(self, tmp_path):
        stages = {T43: _vote(COMPLETION), T44: _vote(COMPLETION)}
        assert _plan(tmp_path, stages, target="fedora-99-x86_64").edits == []

    def test_no_stage_lookup_means_no_removal(self, tmp_path):
        log = _not_found(tmp_path, "/usr/share/bash-completion/completions/hyprctl")
        result = plan("Hyprland", META, log)
        assert result.edits == [] and result.pending

    def test_glob_and_directory_entries_are_removable(self, tmp_path):
        entry_glob = "%{_datadir}/wayland-sessions/hyprland*.desktop"
        stages = {t: _vote(entry_glob) for t in (T43, T44)}
        result = _plan(
            tmp_path, stages, paths=["/usr/share/wayland-sessions/hyprland*.desktop"]
        )
        assert result.edits == [FileEdit("-", "files", entry_glob)]

    def test_the_last_main_entry_is_never_removed(self, tmp_path):
        meta = {"version": "0.57.0", "files": ["%{_bindir}/hyprctl"]}
        stages = {T43: _vote("%{_bindir}/hyprctl"), T44: _vote("%{_bindir}/hyprctl")}
        result = _plan(tmp_path, stages, meta=meta, paths=["/usr/bin/hyprctl"])
        assert result.edits == [] and result.pending == []

    def test_a_missing_file_nobody_declares_changes_nothing(self, tmp_path):
        result = _plan(tmp_path, {}, paths=["/usr/share/other/x"])
        assert result.edits == [] and result.pending == []


class TestPlanAdditions:
    def _unpackaged(self, tmp_path, *paths):
        text = "error: Installed (but unpackaged) file(s) found:\n" + "".join(
            f"   {p}\n" for p in paths
        )
        return _log(tmp_path, text + "Child return code was: 1\n")

    def test_adds_undeclared_files_to_the_right_list(self, tmp_path):
        log = self._unpackaged(
            tmp_path,
            "/usr/lib64/systemd/user/hyprland-session.target",
            "/usr/lib64/pkgconfig/x.pc",
        )
        result = plan("Hyprland", META, log)
        assert result.edits == [
            FileEdit("+", "files", "%{_libdir}/systemd/user/hyprland-session.target"),
            FileEdit("+", "devel.files", "%{_libdir}/pkgconfig/x.pc"),
        ]

    def test_covered_files_are_skipped(self, tmp_path):
        log = self._unpackaged(
            tmp_path, "/usr/include/hyprland/api.h", "/usr/share/hypr/a.conf"
        )
        assert plan("Hyprland", META, log).edits == []

    def test_without_a_devel_package_headers_go_to_main_files(self, tmp_path):
        meta = {"version": "1", "files": ["%{_bindir}/x"]}
        log = self._unpackaged(tmp_path, "/usr/include/x/y.h")
        assert plan("x", meta, log).edits == [
            FileEdit("+", "files", "%{_includedir}/x/y.h")
        ]

    def test_additions_need_no_vote(self, tmp_path):
        log = self._unpackaged(tmp_path, "/usr/bin/new")
        result = plan("Hyprland", META, log, target=T45, targets=TARGETS)
        assert result.edits and not result.pending


@pytest.fixture
def packages_yaml(tmp_path):
    path = tmp_path / "packages.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "Hyprland": {
                    "version": "0.57.0",
                    "files": ["%{_bindir}/b", "%{_bindir}/A", COMPLETION],
                    "devel": {"files": ["%{_includedir}/h/"]},
                },
                "other": {"version": "1", "files": ["%{_bindir}/o"]},
            }
        )
    )
    return path


def _data(path):
    return yaml.safe_load(path.read_text())


class TestApplyEdits:
    def test_adds_sorted_and_deduplicated_and_returns_signed_changes(
        self, packages_yaml
    ):
        changes = apply_edits(
            "Hyprland",
            [
                FileEdit("+", "files", "%{_bindir}/c"),
                FileEdit("+", "files", "%{_bindir}/b"),  # already there
                FileEdit("+", "devel.files", "%{_libdir}/pkgconfig/x.pc"),
            ],
            path=packages_yaml,
        )
        assert changes == [
            "+files:%{_bindir}/c",
            "+devel.files:%{_libdir}/pkgconfig/x.pc",
        ]
        data = _data(packages_yaml)["Hyprland"]
        assert data["files"] == sorted(data["files"], key=str.lower)
        assert "%{_bindir}/c" in data["files"]
        assert data["files"].count("%{_bindir}/b") == 1
        assert data["devel"]["files"] == [
            "%{_includedir}/h/",
            "%{_libdir}/pkgconfig/x.pc",
        ]

    def test_removes(self, packages_yaml):
        changes = apply_edits(
            "Hyprland", [FileEdit("-", "files", COMPLETION)], path=packages_yaml
        )
        assert changes == [f"-files:{COMPLETION}"]
        assert COMPLETION not in _data(packages_yaml)["Hyprland"]["files"]

    def test_removing_the_last_devel_entry_keeps_an_empty_list(self, packages_yaml):
        apply_edits(
            "Hyprland",
            [FileEdit("-", "devel.files", "%{_includedir}/h/")],
            path=packages_yaml,
        )
        assert _data(packages_yaml)["Hyprland"]["devel"]["files"] == []

    def test_removing_an_absent_entry_is_a_no_op_and_writes_nothing(self, packages_yaml):
        before = packages_yaml.read_text()
        changes = apply_edits(
            "Hyprland", [FileEdit("-", "files", "%{_bindir}/nope")], path=packages_yaml
        )
        assert changes == []
        assert packages_yaml.read_text() == before

    def test_other_packages_untouched(self, packages_yaml):
        before = _data(packages_yaml)["other"]
        apply_edits(
            "Hyprland", [FileEdit("+", "files", "%{_bindir}/z")], path=packages_yaml
        )
        assert _data(packages_yaml)["other"] == before

    def test_unknown_package(self, packages_yaml):
        with pytest.raises(KeyError):
            apply_edits("ghost", [FileEdit("+", "files", "x")], path=packages_yaml)
