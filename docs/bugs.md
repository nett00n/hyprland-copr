# Bugs

- `make update-daily` failed because of new dependency for hyprgraphics. deps updated, `make full-cycle PKG=hyprgrafics` was ok, yet `make update-daily` set hyprgraphics to be rebuilt again #low
- make sure copr stage is runned only if rebuilt is really required. If status is still unknown - do not schedule new one
- root cause of the local-repo dependency-conflict issue above: `stage-mock.py:update_local_repo()` copies every newly built RPM into `local-repo/` but never removes the old NVR of the same package -> local-repo only ever grows, `clean-localrepo` is the only fix and it nukes everything
- `lib/github.py:save_release_cache` never evicts old `(url, version)` entries from `cache/github-releases.json`, only TTL-gates read freshness -> file grows forever, one entry per version ever seen for every package
- `cache/` (github release cache) is missing from `.gitignore`, unlike `local-repo/`/`logs/`/`build-report.yaml` -> risk of accidentally committing it
- `~/rpmbuild/{SOURCES,SRPMS}` in each `rpmbuild-<fedora-version>` volume accumulate every historical SRPM/tarball forever (confirmed: `stage-srpm.py:find_srpm` just picks newest by mtime, nothing deletes older ones) -> only "wipe everything" or "remove package entirely" exist, no prune-old-versions-of-a-live-package option
- `lib/yaml_utils.py:init_stage()` wipes the ENTIRE stage dict in build-report.yaml (`build_status["stages"][stage_name] = {}`) whenever PROCEED_BUILD isn't "true", regardless of the PACKAGE filter -> `make stage-mock PACKAGE=hyprland` (no PROCEED_BUILD) destroys every other package's mock-stage status. `full-cycle.py:setup_build_status()` does NOT have this bug (only `.setdefault`, preserves entries) -> same logical action is destructive via `make stage-X` but safe via `make full-cycle`, likely related to the hyprgraphics rebuild-loop entry above
- does hyprpolkit increment release on rebuild, when dependency is updated
- `make add-submodule` doesn't check PACKAGE is set before use -> raw python KeyError instead of friendly error (unlike add-new/delete-package/set-release which do check) #low
- `make container-enter` doesn't match `$(CONTAINER_RUN)`: no `--privileged`, no `.venv`/mock-conf/copr-config mounts -> manual mock testing inside fails differently than real stages
- `save-last-build`, `clean`, `clean-localrepo` skip the `check-image` prereq other targets have -> raw podman/docker error instead of "run make container-build" hint
- `.env` `LOG_LEVEL=""` isn't quote-stripped like FEDORA_VERSION/PACKAGE/etc -> make's `$(if $(LOG_LEVEL),...)` sees non-empty `""` and injects `-e LOG_LEVEL=""` into container instead of leaving unset #low
- Makefile `full-cycle` passes `FORCE_MOCK`/`DRY_RUN` env vars into the container but nothing in scripts/ reads them -> silent no-op flags, misleading
- `scripts/lib/pipeline.py` STAGE_ORDER drops "validate"; `scripts/lib/yaml_utils.py` STAGES has all 6 and is hardcoded again inline at yaml_utils.py:384 instead of reusing the constant -> 3 copies of the stage list, one silently different
- `scripts/lib/gitmodules.py` reimplements git subprocess calls 8x instead of using `lib/subprocess_utils.run_git` -> inconsistent timeouts (some unbounded) and error handling; `fetch_tags` doesn't catch `FileNotFoundError` unlike other git callers
- `scripts/lib/yaml_utils.py:update_package_releases` mutates packages.yaml via regex string substitution on raw text instead of load/mutate/dump like the rest of the module -> fragile, depends on exact indentation matching
- `scripts/validate-packages.py` (the pre-commit gate) and `scripts/lib/validation.py` (used by `stage-validate`, the actual build) are two independent, already-diverged validators for packages.yaml/.gitmodules -> a package can pass pre-commit and still fail build validation, or vice versa

