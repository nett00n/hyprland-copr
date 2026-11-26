"""#COPR-0032: Fedora version constants agree across Makefile and Python, and no
script hardcodes a FEDORA_VERSION fallback."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import paths
from lib.yaml_utils import SUPPORTED_FEDORA_VERSIONS

ROOT = Path(__file__).parent.parent
MAKEFILE = (ROOT / "Makefile").read_text()


def _make_var(name: str) -> str:
    m = re.search(rf"^{name}\s*:?=\s*(.+?)\s*$", MAKEFILE, re.MULTILINE)
    assert m, f"{name} not defined in Makefile"
    return m.group(1)


def test_makefile_supported_matches_python():
    assert set(_make_var("SUPPORTED").split()) == SUPPORTED_FEDORA_VERSIONS


def test_makefile_default_matches_python():
    assert _make_var("DEFAULT_FEDORA_VERSION") == paths.DEFAULT_FEDORA_VERSION


def test_makefile_canonical_matches_python():
    assert _make_var("CANONICAL_FEDORA_VERSION") == paths.CANONICAL_FEDORA_VERSION


def test_makefile_fallback_uses_default_constant():
    assert re.search(
        r"^FEDORA_VERSION\s*\?=\s*\$\(DEFAULT_FEDORA_VERSION\)", MAKEFILE, re.MULTILINE
    )


def test_version_roles_are_consistent():
    versions = sorted(SUPPORTED_FEDORA_VERSIONS, key=int)
    assert paths.CANONICAL_FEDORA_VERSION == versions[0]
    assert paths.RAWHIDE_FEDORA_VERSION == versions[-1]
    assert paths.DEFAULT_FEDORA_VERSION in SUPPORTED_FEDORA_VERSIONS
    assert paths.DEFAULT_FEDORA_VERSION != paths.RAWHIDE_FEDORA_VERSION


def test_46_is_supported_and_default_is_45():
    assert "46" in SUPPORTED_FEDORA_VERSIONS
    assert paths.DEFAULT_FEDORA_VERSION == "45"


def test_no_script_hardcodes_a_fedora_version_fallback():
    pattern = re.compile(r"""environ\.get\(\s*["']FEDORA_VERSION["']\s*,\s*["']\d+["']""")
    offenders = [
        str(p.relative_to(ROOT))
        for p in (ROOT / "scripts").rglob("*.py")
        if pattern.search(p.read_text())
    ]
    assert offenders == []
