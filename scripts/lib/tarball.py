"""Helpers for probing remote tarballs."""

import subprocess


def detect_tarball_source_name(
    tar_urls: list[str], pkg_name: str, version_or_commit: str
) -> str | None:
    """Fetch the first entry from a remote tarball to determine its top-level directory.

    Tries each URL in tar_urls until one yields output (handles both v-prefixed
    and bare version tags). Returns the directory name prefix (e.g. 'Waybar') when
    it differs from '{pkg_name}-{version_or_commit}', otherwise None.
    Streams via curl|tar so only the minimum bytes are downloaded.
    """
    first = ""
    for tar_url in tar_urls:
        try:
            curl_proc = subprocess.Popen(
                ["curl", "-sLf", "--max-time", "30", tar_url],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=60,
            )
            tar_result = subprocess.run(
                ["tar", "-tz"],
                stdin=curl_proc.stdout,
                capture_output=True,
                text=True,
                timeout=60,
            )
            curl_proc.wait(timeout=5)
            if tar_result.returncode == 0:
                first = tar_result.stdout.strip().split("\n")[0].split("/")[0]
            if first:
                break
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            continue
    if not first:
        return None
    expected = f"{pkg_name}-{version_or_commit}"
    if first == expected:
        return None
    # Strip the version/commit suffix to get the bare name prefix
    name_part = first.rsplit("-", 1)[0] if "-" in first else first
    return name_part
