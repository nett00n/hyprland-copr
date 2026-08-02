"""Tests for lib.source_lock (BUG-0025 checksum pinning for upstream sources)."""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from lib import paths
from lib.source_lock import (
    Skip,
    load_lock,
    record,
    remote_sources,
    save_lock,
    sha256_file,
    verify,
)


@pytest.fixture(autouse=True)
def lock_path(tmp_path, monkeypatch):
    """Point lib.paths.SOURCES_LOCK at a fresh tmp file for every test."""
    monkeypatch.setattr(paths, "SOURCES_LOCK", tmp_path / "sources.lock.yaml")
    return tmp_path / "sources.lock.yaml"


class TestRemoteSources:
    """remote_sources() decides what needs a pinned checksum -- getting this
    wrong either lets an unverified file through (excluded when it shouldn't
    be) or wrongly blocks a local-only file (included when it shouldn't be).
    """

    def test_expands_archive_template(self):
        meta = {
            "url": "https://github.com/hyprwm/aquamarine",
            "version": "0.14.0",
            "source": {
                "archives": [
                    "%{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz"
                ]
            },
        }
        out = remote_sources("aquamarine", meta)
        assert out == [
            (
                "aquamarine-0.14.0.tar.gz",
                "https://github.com/hyprwm/aquamarine/archive/refs/tags/v0.14.0.tar.gz#/aquamarine-0.14.0.tar.gz",
            )
        ]

    def test_filename_falls_back_to_url_basename_without_fragment(self):
        meta = {
            "url": "https://sndio.org",
            "version": "1.9.0",
            "source": {"archives": ["https://sndio.org/sndio-%{version}.tar.gz"]},
        }
        out = remote_sources("sndio", meta)
        assert out == [("sndio-1.9.0.tar.gz", "https://sndio.org/sndio-1.9.0.tar.gz")]

    def test_local_vendor_tarball_excluded(self):
        """A bare filename (produced locally by stage-vendor) has no scheme -- it
        isn't something a network download can tamper with, so it's out of scope.
        """
        meta = {
            "url": "https://github.com/Aylur/ags",
            "version": "3.1.2",
            "source": {
                "archives": [
                    "%{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz",
                    "%{name}-%{version}-vendor.tar.gz",
                ]
            },
        }
        out = remote_sources("aylurs-gtk-shell", meta)
        assert len(out) == 1
        assert out[0][0] == "aylurs-gtk-shell-3.1.2.tar.gz"

    def test_bundled_deps_included(self):
        meta = {
            "url": "https://example.com/pkg",
            "version": "1.0",
            "source": {
                "archives": ["%{url}/archive/v%{version}.tar.gz#/%{name}-%{version}.tar.gz"],
                "bundled_deps": [
                    {
                        "name": "libfoo",
                        "version": "2.0",
                        "url": "https://example.com/libfoo-2.0.tar.gz",
                        "source_index": 1,
                    }
                ],
            },
        }
        out = remote_sources("pkg", meta)
        assert ("libfoo-2.0.tar.gz", "https://example.com/libfoo-2.0.tar.gz") in out

    def test_no_archives_returns_empty(self):
        assert remote_sources("pkg", {"source": {}}) == []


class TestSha256File:
    def test_matches_hashlib(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"hello world" * 1000)
        assert sha256_file(f) == hashlib.sha256(b"hello world" * 1000).hexdigest()


class TestVerify:
    """verify() is what stage-srpm.py and the vendor download path fail-close on."""

    META = {
        "url": "https://example.com/pkg",
        "version": "1.0",
        "source": {
            "archives": ["%{url}/archive/v%{version}.tar.gz#/pkg-1.0.tar.gz"]
        },
    }

    def test_clean_when_hash_matches(self, tmp_path):
        f = tmp_path / "pkg-1.0.tar.gz"
        f.write_bytes(b"tarball contents")
        digest = sha256_file(f)
        save_lock({"pkg": {"pkg-1.0.tar.gz": {"sha256": digest, "url": "x"}}})
        assert verify("pkg", self.META, tmp_path) == []

    def test_no_lock_entry_fails_closed(self, tmp_path):
        f = tmp_path / "pkg-1.0.tar.gz"
        f.write_bytes(b"tarball contents")
        problems = verify("pkg", self.META, tmp_path)
        assert len(problems) == 1
        assert "no entry in sources.lock.yaml" in problems[0]
        assert "refresh-checksums PACKAGE=pkg" in problems[0]

    def test_missing_file_reported(self, tmp_path):
        save_lock({"pkg": {"pkg-1.0.tar.gz": {"sha256": "deadbeef", "url": "x"}}})
        problems = verify("pkg", self.META, tmp_path)
        assert len(problems) == 1
        assert "missing from" in problems[0]

    def test_hash_mismatch_reported(self, tmp_path):
        f = tmp_path / "pkg-1.0.tar.gz"
        f.write_bytes(b"tampered contents")
        save_lock({"pkg": {"pkg-1.0.tar.gz": {"sha256": "deadbeef", "url": "x"}}})
        problems = verify("pkg", self.META, tmp_path)
        assert len(problems) == 1
        assert "sha256 mismatch" in problems[0]
        assert "deadbeef" in problems[0]

    def test_package_with_no_remote_sources_is_clean(self, tmp_path):
        assert verify("pkg", {"source": {}}, tmp_path) == []


class TestRecord:
    """record() is the only thing allowed to write sources.lock.yaml."""

    META = {
        "url": "https://example.com/pkg",
        "version": "1.0",
        "source": {
            "archives": ["%{url}/archive/v%{version}.tar.gz#/pkg-1.0.tar.gz"]
        },
    }

    def test_records_new_entry(self, tmp_path):
        f = tmp_path / "pkg-1.0.tar.gz"
        f.write_bytes(b"tarball contents")
        recorded, skipped = record("pkg", self.META, tmp_path)
        assert skipped == []
        assert recorded == {"pkg-1.0.tar.gz": sha256_file(f)}

        lock = load_lock()
        entry = lock["pkg"]["pkg-1.0.tar.gz"]
        assert entry["sha256"] == sha256_file(f)
        assert entry["size"] == f.stat().st_size
        assert "recorded" in entry
        assert entry["url"].endswith("pkg-1.0.tar.gz")

    def test_missing_file_skipped_not_recorded(self, tmp_path):
        recorded, skipped = record("pkg", self.META, tmp_path)
        assert recorded == {}
        assert len(skipped) == 1
        assert skipped[0].conflict is False
        assert load_lock() == {}

    def test_refuses_to_overwrite_differing_hash_without_force(self, tmp_path):
        f = tmp_path / "pkg-1.0.tar.gz"
        f.write_bytes(b"new contents")
        save_lock({"pkg": {"pkg-1.0.tar.gz": {"sha256": "deadbeef", "url": "x"}}})

        recorded, skipped = record("pkg", self.META, tmp_path)

        assert recorded == {}
        assert len(skipped) == 1
        assert skipped[0].conflict is True
        # Original entry untouched.
        assert load_lock()["pkg"]["pkg-1.0.tar.gz"]["sha256"] == "deadbeef"

    def test_force_overwrites_differing_hash(self, tmp_path):
        f = tmp_path / "pkg-1.0.tar.gz"
        f.write_bytes(b"new contents")
        save_lock({"pkg": {"pkg-1.0.tar.gz": {"sha256": "deadbeef", "url": "x"}}})

        recorded, skipped = record("pkg", self.META, tmp_path, force=True)

        assert skipped == []
        assert recorded == {"pkg-1.0.tar.gz": sha256_file(f)}
        assert load_lock()["pkg"]["pkg-1.0.tar.gz"]["sha256"] == sha256_file(f)

    def test_recording_same_hash_again_is_not_a_conflict(self, tmp_path):
        f = tmp_path / "pkg-1.0.tar.gz"
        f.write_bytes(b"tarball contents")
        record("pkg", self.META, tmp_path)
        recorded, skipped = record("pkg", self.META, tmp_path)
        assert skipped == []
        assert recorded == {"pkg-1.0.tar.gz": sha256_file(f)}

    def test_other_packages_untouched(self, tmp_path):
        save_lock({"other-pkg": {"other.tar.gz": {"sha256": "abc", "url": "x"}}})
        f = tmp_path / "pkg-1.0.tar.gz"
        f.write_bytes(b"tarball contents")
        record("pkg", self.META, tmp_path)
        lock = load_lock()
        assert "other-pkg" in lock
        assert lock["other-pkg"]["other.tar.gz"]["sha256"] == "abc"


class TestSkipRepr:
    def test_repr_includes_conflict_flag(self):
        s = Skip("f.tar.gz", "some reason", conflict=True)
        assert "conflict=True" in repr(s)
