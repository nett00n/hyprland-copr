"""Utilities for generating spec files from package metadata."""


def process_archive_urls(
    archives: list,
    pkg_url: str,
    pkg_name: str,
    commit: dict | None = None,
    version: str = "",
) -> list:
    """Expand %{url}, %{name}, %{commit}, %{shortcommit}, %{version} in archive templates.

    Strips .git from pkg_url — GitHub archive endpoints do not accept it.

    Args:
        archives: List of archive URL templates from packages.yaml
        pkg_url: Package URL (may end with .git)
        pkg_name: Package name (will be lowercased)
        commit: Optional commit dict with 'full' key (40-char hash)
        version: Package version to expand in templates

    Returns:
        List of processed archive URLs with all known values expanded
    """
    url = pkg_url.rstrip("/").removesuffix(".git")
    commit_full = (commit or {}).get("full", "")
    commit_short = commit_full[:7] if commit_full else ""
    name = pkg_name.lower()

    result = []
    for archive in archives:
        if not isinstance(archive, str):
            result.append(archive)
            continue
        # Expand all known values
        a = archive.replace("%{url}", url).replace("%{name}", name)
        if version and "%{version}" in a:
            a = a.replace("%{version}", version)
        if commit_full and "%{commit}" in a:
            a = a.replace("%{commit}", commit_full)
        if commit_short and "%{shortcommit}" in a:
            a = a.replace("%{shortcommit}", commit_short)
        result.append(a)
    return result
