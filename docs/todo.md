# Features

- Add ARM64 local build support. We did not encounter arch-tangled errors. Yet
- Add cross-os-version build matrix visualization
- Separate prod builds and local debug ones (?)
- add make fmt after scaffolding
- \*-git packages to separate block
- #2.0 split management system and hyprland repo content. Make automations repo a submodule of content repo (?)

# Containers / caches

- `/var/lib/mock` (mock's own chroot cache) isn't mounted as a volume like `rpmbuild`/`local-repo` are -> since containers run `--rm`, every fresh `make stage-mock` run rebuilds/bootstraps the whole chroot from scratch instead of reusing a cached one, costing real time on every `update-daily`. Would need cache-invalidation handling if persisted, since a stale local-repo (see bugs.md) could then poison a persisted chroot's dnf cache too

# Build report data model

- build-report.yaml has no per-Fedora-version key -> one slot per (stage, package), rebuilding for a 2nd OS version overwrites the 1st version's result. `run.fedora_version` is also a single global field
- only "last attempt" is stored, not "last success" -> a failed rebuild overwrites the previous known-good version/log/build_id, no `last_success` kept alongside `last_attempt`
- `save_build_status()` rewrites the whole file (175KB/4093 lines today, 44 pkgs x 6 stages) once per package inside the build loop -> O(n^2) I/O, only there for crash-resilience checkpointing
- decide: yaml vs sqlite for build-report. build-report.yaml is gitignored (not committed) so "diffable in git" isn't a real argument for keeping yaml; sqlite (stdlib, no new dep) would give (package, stage, fedora_version, attempt_type) as a real composite key + cheap row upserts instead of full-file rewrites, at the cost of losing quick cat/grep debugging and requiring gen-report.py/stage-show-plan.py to move off yaml.safe_load

# Makefile

- PACKAGE var means 3 different things (single name / comma-list in set-release / rpm path in gather-requires) with no validation -> split into separate vars or document+enforce per-target
- two different multi-package loop strategies coexist: Makefile-side `_PKGS` loop (sources, stage-log-analyze) vs pass-PACKAGE-to-python (all stage-* targets) -> pick one
- HIGHLIGHT_PREFIX default bakes literal quote chars into value as a hack so unquoted `echo $(HIGHLIGHT_PREFIX) "text"` works; check-image/check-venv/setup-volumes instead embed it inside a quoted string -> fragile, one edit away from breaking output. simplify to plain value + consistent quoting everywhere
- ALL_PACKAGES parses packages.yaml with a grep regex instead of the yaml lib used everywhere else (scripts/*.py, inline python in delete-package/add-submodule) -> fragile, switch to yaml
- delete-package/add-submodule/add-new embed real logic (yaml edits, git submodule surgery) directly in Makefile recipes instead of scripts/*.py -> untestable by pytest, move to scripts
- update-daily forks 5 separate `$(MAKE)` sub-processes (update-versions, fmt, full-cycle, readme, copr-description), each re-runs check-image/check-venv/setup-volumes from scratch -> combine into one `$(MAKE) a b c` call like pre-commit does
- delete-package purges rpmbuild-* volumes for removed package across SUPPORTED versions but never touches local-repo-* volumes -> stale RPMs linger

# Scripts

- `scripts/gen-spec.py` (~440 lines) duplicates `lib/github.py` (release cache, changelog) and `lib/config.get_packager` almost verbatim, has no Makefile target, unused except by its own test -> looks like a dead pre-pipeline prototype, remove or replace with lib calls
- `scripts/validate-package-urls.py` is dead code, zero references outside its own test -> remove
- `tests/conftest.py` and `tests/integration/conftest.py` are ~95% identical (fake_repo/fake_build_status/minimal_package fixtures copy-pasted), even though tests/integration/ already inherits the parent conftest -> dedupe
- `scripts/full-cycle.py:run_build_pipeline` has ~320 lines of repeated per-stage orchestration (spec/vendor/srpm/mock/copr all same shape: cache check -> run_for_package -> inject_stage_meta -> save_build_status) -> candidate for a small stage-runner abstraction
- each `stage-*.py` (validate/spec/vendor/srpm/mock/copr) copy-pastes its own "config: skip" result dict (~6-8 lines x6) -> extract to a `lib/stage_utils` helper
- 9 top-level scripts have zero tests: format-yaml, gather-requires, list-tags, pkg-build-pop, pkg-log-analysis, rpm-dir-prefixes-convert, set-package-release, sort-yaml-lists, validate-packages -> violates project's own TDD rule; worst offenders are the two regex-based YAML block parsers (sort-yaml-lists.py, rpm-dir-prefixes-convert.py) and validate-packages.py itself (the pre-commit gate)
- `scripts/lib/log_analysis.py` (944 lines) is ~30 copy-pasted `if m: issues.append(...); continue` blocks from hand-written regexes -> a data table of (regex, formatter) pairs would cut it by half+
- `vendor_golang.py`/`vendor_rust.py` hand-roll subprocess+log-writing instead of using `lib/subprocess_utils.run_cmd`, which already does exactly that
- `vendor.py`/`vendor_golang.py`/`vendor_rust.py` have asymmetric interfaces (Go: dispatcher downloads+extracts then calls generate(src_dir); Rust: generate() does its own download/extract/tarball internally) -> no shared per-language template, drifted independently
- 3 YAML modules (`yaml_config.py`, `yaml_utils.py`, `yaml_format.py`) mix PyYAML-load + ruamel-dump inconsistently with no doc on which to use when -> confusing for newcomers
- dead code: `lib/reporting.badge()` (only `badge_short()` is used), `lib/yaml_utils.load_packages` alias (only `get_packages` is used) -> remove
- `scripts/set-package-release.py` has a redundant manual `sys.path.insert` that no other script needs -> remove
- `scripts/serve.py` (dev HTTP server) has no Makefile target and no tests, only mentioned in CONTRIBUTING.md -> confirm still needed or drop
- `scripts/pkg-log-analysis.py` imports underscore-prefixed "private" functions directly from `lib.log_analysis` -> either make them public API or move this script's logic into lib/
- `Containerfile` installs cargo/golang/mock/rpmlint with no version pins -> minor reproducibility risk over time

# Packages

everything, that Hyprland recommended:
- https://github.com/MalpenZibo/ashell #Rust
- https://codeberg.org/LGFae/awww #Rust
- https://gmithub.com/anufrievroman/waypaper
- https://github.com/davatorium/rofi
- https://github.com/philj56/tofi
- https://github.com/anyrun-org/anyrun #Rust
- https://github.com/abenz1267/walker #Rust
- https://github.com/vicinaehq/vicinae
- https://github.com/Linus789/wl-clip-persist #Rust
- https://github.com/rolv-apneseth/clipvault #Rust
- https://github.com/savedra1/clipse
- https://github.com/Sirulex/cursor-clip #Rust
- https://github.com/gokcehan/lf
- https://github.com/yorukot/superfile
- https://github.com/sxyazi/yazi #Rust
- https://github.com/kaii-lb/overskride #Rust
- https://github.com/linuxmint/blueberry
- https://github.com/J-Lentz/iwgtk
- https://github.com/loqusion/hyprshade
- https://github.com/hyprland-community/hyprland-rs #Rust
- https://github.com/kosa12/hyprKCS #Rust
- https://github.com/hyprland-community/hyprls
- https://github.com/zjeffer/split-monitor-workspaces
- https://hyprtile.org/#download (?) is not git-published at first glance
- https://github.com/outfoxxed/hy3
- https://github.com/levnikmyskin/hyprland-virtual-desktops
- https://github.com/zakk4223/hyprland-easymotion

seems interesting:
- https://github.com/noctalia-dev/noctalia
- https://github.com/jjsullivan5196/wvkbd
- https://github.com/hbuddenberg/hyprcaffeine
- https://github.com/loqusion/hyprshade
- https://danklinux.com/
- https://github.com/amarqs182/hyprcaffeine
- https://github.com/hbuddenberg/hyprcaffeine
- https://github.com/funinkina/openeffects
- https://github.com/AprilNEA/OpenLogi
- https://github.com/gnomeria/usbtree

hyprland-plugins:
- https://github.com/fedsfarm/gloview
- https://github.com/yayuuu/hyprland-scroll-overview
- https://github.com/surprizeattackxx-dotcom/hypr-gamma
- https://github.com/raybbian/hyprtasking
- https://github.com/SsubezZ/hyprtoplr
- https://github.com/0xFMD/hyprmodoro
- https://github.com/alexhulbert/Hyprchroma
- https://github.com/VirtCode/hypr-dynamic-cursors
- https://github.com/zakk4223/hyprland-easymotion
- https://github.com/KZDKM/Hyprspace
- https://github.com/ernestoCruz05/hycov
- https://github.com/micha4w/Hypr-DarkWindow
- https://github.com/levnikmyskin/hyprland-virtual-desktops
- https://github.com/outfoxxed/hy3
- https://github.com/ItsDrike/hyprland-dwindle-autogroup
- https://github.com/pyt0xic/hyprfocus
- https://github.com/zakk4223/hyprRiver
- https://github.com/zakk4223/hyprNStack
- https://github.com/horriblename/hyprgrass
- https://github.com/zjeffer/split-monitor-workspaces

