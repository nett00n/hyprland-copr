# Load .env file if it exists (allows declaring defaults without overriding env exports)
-include .env
# Strip quotes from .env variables (shell syntax vs make syntax)
FEDORA_VERSION  := $(subst ",,$(FEDORA_VERSION))
COPR_REPO       := $(subst ",,$(COPR_REPO))
PACKAGE         := $(subst ",,$(PACKAGE))
SKIP_PACKAGES   := $(subst ",,$(SKIP_PACKAGES))
LOG_LEVEL       := $(subst ",,$(LOG_LEVEL))
CMD_TIMEOUT     := $(subst ",,$(CMD_TIMEOUT))
# Fallback defaults if not set after stripping
FEDORA_VERSION  ?= 44
SUPPORTED        := 43 44 45
# Mirrors scripts/lib/paths.py's CANONICAL_FEDORA_VERSION -- the one matrix
# chroot full-cycle-matrix treats as authoritative (release bumps, and the
# spec/srpm stage-copr.py submits from). Keep the two in sync by hand; no
# single source of truth crosses the Make/Python boundary here, same as
# SUPPORTED/SUPPORTED_FEDORA_VERSIONS already don't.
CANONICAL_FEDORA_VERSION := 43
IMAGE_NAME       := rpm-toolbox
HIGHLIGHT_PREFIX ?= "█▓▒░"

# Accept either PACKAGE or PKG; PACKAGE takes precedence
PACKAGE      ?=
PKG          ?=
PACKAGE      := $(or $(PACKAGE),$(PKG))

# Skip packages during dependency gathering (comma-separated list)
SKIP_PACKAGES ?=

# Log level: DEBUG, INFO (default), WARNING, ERROR, CRITICAL
LOG_LEVEL    ?=
# Command timeout in seconds (default 3600/60min, for long builds like mock)
CMD_TIMEOUT  ?=
MAKE_LOGS_DIR := ./logs/make

MOCK_CHROOT := fedora-$(FEDORA_VERSION)-x86_64

# Container runtime: podman (default) or docker (fallback)
CONTAINER_RUNTIME ?= $(shell command -v podman >/dev/null 2>&1 && echo podman || echo docker)
CONTAINER_SUDO    := $(if $(filter docker,$(CONTAINER_RUNTIME)),sudo,)

# Only allocate a pty for the container (-t) when make's own stdout is one --
# without this, lib.reporting's colorized stage=/state= event lines are always
# invisible to isatty() inside the container, even run interactively from a
# real terminal (podman/docker give a plain pipe without -t). Piped/CI/non-tty
# invocations correctly get no -t, same as the no-container path already does.
# MAKE_TERMOUT (GNU Make >=4.1) is the name of make's own stdout terminal when
# it is one -- `$(shell test -t 1 ...)` doesn't work here: $(shell) always
# captures its subshell's stdout through a pipe to get the function's return
# value, so `test -t 1` inside it sees that pipe, never the real terminal.
MAKE_TTY := $(if $(MAKE_TERMOUT),-t,)

# NO_CONTAINER=1 runs lint/test natively (no podman/docker) -- for CI, which is
# already a disposable container with no privilege for nested --privileged runs.
# Only lint/test targets are guaranteed to work this way; build/mock/copr stages
# still require the containerized toolchain (mock, cargo, golang) and are
# untouched by this flag.
NO_CONTAINER ?=

# User ID/GID detection for rootless containers
USER_ID      := $(shell id -u)
GROUP_ID     := $(shell id -g)
HOME_DIR     := $(shell echo $$HOME)

# Single container image builds every chroot via `mock -r`, so ~/rpmbuild is
# shared across FEDORA_VERSION values rather than one volume per version --
# that's what makes "one spec, one SRPM" true by construction: there is only
# ever one ~/rpmbuild/SRPMS to build into or read from (container user is set
# in Containerfile).
RPMBUILD_VOLUME  := rpmbuild
RPMBUILD_MOUNT   := $(RPMBUILD_VOLUME):/root/rpmbuild:z
# Persist mock's buildroot cache/state across --rm containers (TODO-0014) so a
# fresh `make full-cycle`/nightly run doesn't re-bootstrap every chroot from
# scratch. Deliberately left owned by root (mock's own layout, root:mock
# 2775) -- unlike RPMBUILD above, setup-volumes does not chown these.
# Still per-FEDORA_VERSION: mock already namespaces its own cache/root state by
# chroot internally, so sharing these across versions would be redundant
# nesting, not a correctness requirement the way RPMBUILD above is -- and
# de-versioning them would discard every host's existing warm buildroot cache
# for no benefit. Left alone deliberately (see docs/features/COPR-0019-build-target.md).
MOCKCACHE_VOLUME := mock-cache-$(FEDORA_VERSION)
MOCKCACHE_MOUNT  := $(MOCKCACHE_VOLUME):/var/cache/mock:z
MOCKROOT_VOLUME  := mock-root-$(FEDORA_VERSION)
MOCKROOT_MOUNT   := $(MOCKROOT_VOLUME):/var/lib/mock:z
WORKDIR_MOUNT    := $(PWD):/work:z
VENV_MOUNT       := $(PWD)/.venv:/work/.venv:z
COPR_MOUNT_OPT   := ro,z
COPR_CONFIG_MOUNT := $(if $(COPR_REPO),-v $(HOME_DIR)/.config/copr:/root/.config/copr:$(COPR_MOUNT_OPT),)

# local-repo/$(MOCK_CHROOT)/ (the dnf repo dep resolution reads) is a plain
# per-target directory under the /work bind mount, not a podman volume -- see
# docs/CHANGELOG.md 2026-08-11. MOCK_CHROOT (above) is already the same chroot
# triple lib.paths.local_repo()/resolve_target() key on, so it's reused here
# rather than adding a second, redundant variable.
# LOCALREPO_VOLUME itself is no longer created/mounted anywhere -- kept only so
# container-volume-clean can still sweep it off machines from before this
# change. Remove this var and its use below after one cycle.
LOCALREPO_VOLUME := local-repo-$(FEDORA_VERSION)

# Volume mounts + env passthrough shared by every container invocation that
# needs the full mock/copr/venv setup (CONTAINER_RUN below and
# `container-enter`, see #BUG-0006 -- container-enter used to hand-copy only
# two of these five mounts, so mock testing inside it failed differently than
# a real stage's CONTAINER_RUN).
CONTAINER_MOUNTS := \
	-v $(RPMBUILD_MOUNT) \
	-v $(MOCKCACHE_MOUNT) \
	-v $(MOCKROOT_MOUNT) \
	-v $(WORKDIR_MOUNT) \
	-v $(VENV_MOUNT) \
	$(COPR_CONFIG_MOUNT) \
	$(if $(LOG_LEVEL),-e LOG_LEVEL=$(LOG_LEVEL),) \
	$(if $(NO_COLOR),-e NO_COLOR=$(NO_COLOR),)

# Container execution with volume mounts
# Note: Containerfile already sets USER, so don't override it here
# --privileged flag is required for mock to work (namespace support)
ifeq ($(NO_CONTAINER),1)
CONTAINER_RUN    :=
CONTAINER_PYTHON := .venv/bin/python3
RPMLINT          := .venv/bin/rpmlint
WORK             := .
else
CONTAINER_RUN := $(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run --rm --privileged $(MAKE_TTY) \
	$(CONTAINER_MOUNTS) \
	-w /work \
	$(IMAGE_NAME)

# Python in container using mounted .venv
CONTAINER_PYTHON := $(CONTAINER_RUN) /work/.venv/bin/python3
RPMLINT          := rpmlint
WORK             := /work
endif

ALL_PACKAGES := $(shell grep -oP '^[a-zA-Z][a-zA-Z0-9_-]+(?=:)' packages.yaml)
# PACKAGE is comma-separated everywhere else (stage-*, full-cycle, build-pop, set-release);
# normalize commas to spaces here too so sources/stage-log-analyze's shell `for` loop accepts
# the same shape instead of treating "a,b" as one bogus package name (see docs/TODO.md TODO-0029).
comma        := ,
empty        :=
space        := $(empty) $(empty)
_PKGS        := $(if $(PACKAGE),$(subst $(comma),$(space),$(PACKAGE)),$(ALL_PACKAGES))

PYTHON           := .venv/bin/python3
README_COPR      := docs/README.copr.md
COPR_INSTRUCTIONS := docs/INSTALL.copr.md

# Helper: run command, echo success/failure
# Usage: $(call run_with_result,command,success_msg,fail_msg)
define run_with_result
	@$1 && echo $(HIGHLIGHT_PREFIX) "✓ $2" || (echo $(HIGHLIGHT_PREFIX) "✗ $3"; exit 1)
endef

# Concurrency guard (docs/BUGS.md BUG-0043): update-daily/full-cycle/full-cycle-matrix
# each flock this file before doing any work, so two overlapping runs refuse instead
# of corrupting build-report.db, the shared podman volumes, or the git index. Not a
# shared $(call ...) macro: make only recurses under `-n` when "$(MAKE)" is literal
# text in the target's own recipe, so each guard is written out per-target.
PIPELINE_LOCK_FILE ?= logs/.pipeline.lock
PIPELINE_LOCK_HELD ?= # set below before recursing, so nested targets skip the lock instead of deadlocking on it
LOCK_DISABLE ?= # bypass for hosts without flock, or a deliberate parallel run


.DEFAULT_GOAL := help
.PHONY: help setup-venv install-dev setup-volumes test coverage lint lint-ruff lint-flake lint-mypy lint-yaml lint-rpm fmt fmt-ruff fmt-yaml validate-packages pre-commit update-versions list-tags scaffold-package add-submodule add-new delete-package set-release gather-requires gen-report readme readme-shell copr-description normalize-paths sort-lists container-build container-enter container-clean container-volume-clean container-all sources full-cycle _full-cycle full-cycle-matrix _full-cycle-matrix update-daily _update-daily build-pop stage-validate stage-show-plan stage-spec stage-vendor refresh-checksums check-checksums stage-srpm stage-mock stage-copr stage-log-analyze prune-logs check-image check-venv save-last-build clean clean-logs clean-localrepo clean-mock-cache clean-all db-usage db-prune db-shell db-export db-nuke submodules-update submodules-purge sync-hard-reset

save-last-build: ## Save a build-report.db snapshot before clean (local-repo/ is a plain source-tree directory now, not volume-backed, so `clean`/`clean-logs` never touch its RPMs -- see docs/CHANGELOG.md 2026-08-11)
	@mkdir -p logs
	@[ -f build-report.db ] && cp build-report.db logs/build-report.db.last || true
	@echo $(HIGHLIGHT_PREFIX) "✓ Saved build-report.db snapshot to logs/build-report.db.last"

clean-logs: check-image check-venv setup-volumes ## Remove build logs; clears stage/run state but keeps the artifact ledger (use db-nuke to also drop that)
	@rm -rf logs/runs logs/make
	@[ -f build-report.db ] && $(CONTAINER_PYTHON) scripts/db-artifacts.py --reset || true
	@echo $(HIGHLIGHT_PREFIX) "✓ Cleaned build logs and stage state (artifact ledger preserved)"

clean-localrepo: check-image clean-mock-cache ## Purge local repo for FEDORA_VERSION/MOCK_CHROOT to resolve dependency conflicts
	@rm -rf local-repo/$(MOCK_CHROOT)
	@[ -f build-report.db ] && $(CONTAINER_PYTHON) scripts/db-artifacts.py --forget-repo $(MOCK_CHROOT) || true
	@echo $(HIGHLIGHT_PREFIX) "✓ Cleaned local repo: local-repo/$(MOCK_CHROOT)"

clean-mock-cache: ## Drop the persisted mock buildroot cache for FEDORA_VERSION (forces a full re-bootstrap next build; see docs/TODO.md TODO-0014)
	@$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(MOCKCACHE_VOLUME) >/dev/null 2>&1 && \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume rm $(MOCKCACHE_VOLUME) || true
	@$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(MOCKROOT_VOLUME) >/dev/null 2>&1 && \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume rm $(MOCKROOT_VOLUME) || true
	@echo $(HIGHLIGHT_PREFIX) "✓ Cleaned mock cache: $(MOCKCACHE_VOLUME), $(MOCKROOT_VOLUME)"

clean-all: clean-logs clean-localrepo ## Clean logs, local repo, and mock cache; build-report.db's artifact ledger survives (see db-nuke)
	@echo $(HIGHLIGHT_PREFIX) "✓ Full cleanup completed"

clean: save-last-build clean-logs ## Remove build logs (saves last build first)

submodules-update: ## Sync submodule working trees to the commit recorded in git (safe, does not touch the main repo)
	@git submodule sync --recursive
	@git submodule update --init --recursive --force
	@echo $(HIGHLIGHT_PREFIX) "✓ Submodules synced to git-tracked state"

submodules-purge: ## Deinit and wipe all submodule working trees + cached git data (irreversible; confirmation required; re-run submodules-update to restore)
	@printf "$(HIGHLIGHT_PREFIX) Purge all submodule working trees and cached git data? [y/N] "; \
		read ans; \
		[ "$$ans" = "y" ] || [ "$$ans" = "Y" ] || { echo "$(HIGHLIGHT_PREFIX) Aborted."; exit 1; }
	@git submodule deinit -f --all
	@rm -rf .git/modules/submodules
	@echo $(HIGHLIGHT_PREFIX) "✓ Purged submodule working trees and cached data"

sync-hard-reset: ## Hard-reset repo+submodules to origin/<current branch>, stashing/reapplying uncommitted main-repo changes; keeps .env* and build-report.db/.yaml (ignored, so `clean -x` would otherwise purge them) (resolves submodule conflicts; confirmation required)
	@printf "$(HIGHLIGHT_PREFIX) Hard-reset repo and all submodules to origin/$$(git branch --show-current)? [y/N] "; \
		read ans; \
		[ "$$ans" = "y" ] || [ "$$ans" = "Y" ] || { echo "$(HIGHLIGHT_PREFIX) Aborted."; exit 1; }
	@branch=$$(git branch --show-current); \
		stashed=0; \
		if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$$(git status --porcelain --untracked-files=normal -- . ':!submodules')" ]; then \
			git stash push -u -m "pre-reset-backup-$$(date +%s)" || exit 1; \
			stashed=1; \
		fi; \
		git fetch origin || exit 1; \
		git reset --hard "origin/$$branch" || exit 1; \
		git clean -ffdx -e '.env' -e '.env.*' -e 'build-report.db' -e 'build-report.db-*' -e 'build-report.yaml' -e 'build-report.*.yaml' || exit 1; \
		git submodule sync --recursive || exit 1; \
		git submodule update --init --recursive --force || exit 1; \
		git submodule foreach --recursive 'git clean -ffdx' || exit 1; \
		if [ "$$stashed" -eq 1 ]; then \
			git stash pop || (echo "$(HIGHLIGHT_PREFIX) ✗ stash pop conflict -- resolve manually, changes remain in git stash list"; exit 1); \
		fi; \
		echo $(HIGHLIGHT_PREFIX) "✓ Repo and submodules reset to origin/$$branch"

# Prerequisite checks - fail fast on missing dependencies
check-image: ## Verify the (single, version-independent) container image exists (no-op under NO_CONTAINER=1)
ifeq ($(NO_CONTAINER),1)
	@true
else
	@$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) image inspect $(IMAGE_NAME) >/dev/null 2>&1 || \
		(echo "$(HIGHLIGHT_PREFIX) ✗ Container image not found: $(IMAGE_NAME)"; \
		 echo "$(HIGHLIGHT_PREFIX) Run: make container-build"; exit 1)
endif

check-venv: ## Verify .venv exists and has Python
	@test -x .venv/bin/python3 || \
		(echo "$(HIGHLIGHT_PREFIX) ✗ Python venv not found or broken: .venv/bin/python3"; \
		 echo "$(HIGHLIGHT_PREFIX) Run: make setup-venv"; exit 1)

# Setup container volumes with correct permissions - required for rpmbuild and repo operations
setup-volumes: check-image ## Initialize rpmbuild volume (correct UID/GID) and local-repo/$(MOCK_CHROOT)/ dir (no-op under NO_CONTAINER=1)
	@mkdir -p local-repo/$(MOCK_CHROOT)
ifeq ($(NO_CONTAINER),1)
	@true
else
	@$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(RPMBUILD_VOLUME) >/dev/null 2>&1 || \
		($(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume create $(RPMBUILD_VOLUME) || exit 1; \
		 $(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run --rm -v $(RPMBUILD_MOUNT) $(IMAGE_NAME) \
		 	chown -R $(USER_ID):$(GROUP_ID) /root/rpmbuild || exit 1)
	@$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(MOCKCACHE_VOLUME) >/dev/null 2>&1 || \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume create $(MOCKCACHE_VOLUME) || exit 1
	@$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(MOCKROOT_VOLUME) >/dev/null 2>&1 || \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume create $(MOCKROOT_VOLUME) || exit 1
	@echo "$(HIGHLIGHT_PREFIX) ✓ Volumes ready"
endif

help: ## Show this help
	@echo "Usage: make [TARGET] [PACKAGE=<name>] [FEDORA_VERSION=<version>] [LOG_LEVEL=<level>] [CMD_TIMEOUT=<seconds>]"
	@echo ""
	@echo "  Supported versions : $(SUPPORTED)"
	@echo "  Default version    : 44"
	@echo "  Default LOG_LEVEL  : INFO"
	@echo "  Default CMD_TIMEOUT: 3600 (60 minutes)"
	@echo ""
	@echo "  Common workflows:"
	@echo "    make sources PACKAGE=hyprland"
	@echo "    make stage-spec PACKAGE=hyprland"
	@echo "    make stage-mock PACKAGE=hyprland FEDORA_VERSION=44"
	@echo "    make stage-mock PACKAGE=hyprland CMD_TIMEOUT=7200  # 2 hours for large builds"
	@echo "    make full-cycle PACKAGE=hyprland COPR_REPO=nett00n/hyprland"
	@echo "    make full-cycle PACKAGE=hyprland FORCE_REBUILD=1  # ignore cache, rebuild spec through copr"
	@echo ""
	@echo "  Cleanup (when dependency conflicts occur):"
	@echo "    make clean              # Remove build logs"
	@echo "    make clean-localrepo    # Clear local repo RPMs (resolve conflicts)"
	@echo "    make clean-all          # Remove logs and local repo"
	@echo ""
	@echo "  Submodules / git sync:"
	@echo "    make submodules-update  # Sync submodules to git-tracked state (safe)"
	@echo "    make submodules-purge   # Deinit + wipe all submodule working trees (destructive)"
	@echo "    make sync-hard-reset    # Hard-reset repo+submodules to origin (destructive; resolves conflicts)"
	@echo ""
	@echo "  Build artifact tracking (build-report.db):"
	@echo "    make db-usage           # Disk usage by package/target (VERIFY=1: flag corruption)"
	@echo "    make db-prune           # Reclaim space (dry-run; CONFIRM=1 to delete)"
	@echo "    make db-shell           # Interactive sqlite3 shell"
	@echo "    make db-export          # Snapshot for offline diffing (FORMAT=yaml|json, OUTPUT=path)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*## ' Makefile | \
		awk -F': ' '{split($$1, parts, " "); split($$2, desc, "## "); printf "  \033[36m%-24s\033[0m %s\n", parts[1], desc[2]}'

setup-venv: ## Create .venv and install Python dependencies
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt

install-dev: check-image setup-venv setup-volumes ## Install dev tooling (requirements-dev.txt) into .venv
	@$(CONTAINER_PYTHON) -m pip install -q -r requirements-dev.txt

test: check-image check-venv setup-volumes ## Run unit tests for scripts/ using pytest
	$(call run_with_result,$(CONTAINER_PYTHON) -m pytest tests/ -v,Tests passed,Tests failed)

coverage: install-dev ## Run tests with coverage report (--format html for HTML output)
	@mkdir -p "$(MAKE_LOGS_DIR)/coverage"
	@echo "$(HIGHLIGHT_PREFIX) Running coverage analysis..."
	@$(CONTAINER_PYTHON) -m pytest tests/ --cov=scripts --cov-report=term-missing:skip-covered --cov-report=html:.htmlcov -q || exit 1
	@echo "$(HIGHLIGHT_PREFIX) ✓ Coverage report generated"
	@echo "$(HIGHLIGHT_PREFIX) HTML report: .htmlcov/index.html"
	@$(CONTAINER_PYTHON) -m pytest tests/ --cov=scripts --cov-report=json:.htmlcov/coverage.json -q >/dev/null 2>&1 || true

lint: lint-ruff lint-flake lint-mypy lint-rpm lint-yaml ## Run all linters inside container

lint-ruff: install-dev ## Run ruff check on scripts
	$(call run_with_result,$(CONTAINER_PYTHON) -m ruff check scripts/,Ruff check passed,Ruff check failed)

lint-flake: install-dev ## Run flake8 style checker on scripts
	$(call run_with_result,$(CONTAINER_PYTHON) -m flake8 scripts/,Flake8 check passed,Flake8 check failed)

lint-mypy: install-dev ## Run mypy type checker on scripts
	$(call run_with_result,$(CONTAINER_PYTHON) -m mypy scripts/,Mypy check passed,Mypy check failed)

lint-rpm: install-dev ## Run rpmlint on all generated spec files
	$(call run_with_result,$(CONTAINER_RUN) $(RPMLINT) -r $(WORK)/.rpmlintrc --ignore-unused-rpmlintrc packages/*/[a-z]*.spec,Rpmlint check passed,Rpmlint check failed)

lint-yaml: install-dev ## Run yamllint on YAML files
	$(call run_with_result,$(CONTAINER_PYTHON) -m yamllint *.yaml,Yamllint check passed,Yamllint check failed)

fmt: fmt-ruff fmt-yaml normalize-paths sort-lists ## Format and normalize all files

fmt-ruff: install-dev ## Run ruff format on scripts
	$(call run_with_result,$(CONTAINER_PYTHON) -m ruff format scripts/,Ruff format applied,Ruff format failed)

fmt-yaml: check-image check-venv setup-volumes ## Format YAML files with consistent style
	$(call run_with_result,$(CONTAINER_PYTHON) scripts/format-yaml.py '*.yaml',YAML format applied,YAML format failed)

validate-packages: check-venv ## Validate packages.yaml and .gitmodules structure (fast, no container)
	@$(PYTHON) scripts/validate-packages.py

pre-commit: check-venv validate-packages ## Run all checks and formatting (test + lint + fmt). Use COVERAGE=1 to include coverage report
	$(MAKE) test lint fmt || exit 1
	@if [ "$(COVERAGE)" = "1" ]; then \
		echo "$(HIGHLIGHT_PREFIX) Running coverage analysis..."; \
		$(MAKE) coverage || exit 1; \
	fi

update-versions: check-image check-venv setup-volumes ## Fetch latest semver tags from submodules and update packages.yaml
	$(CONTAINER_PYTHON) scripts/update-versions.py

list-tags: check-image check-venv setup-volumes ## List all tags for submodules, highlighting latest semver (PACKAGE=<name>, single package only, for one)
	@case "$(PACKAGE)" in *,*) echo "$(HIGHLIGHT_PREFIX) Error: PACKAGE must be a single package name here (got a comma-separated list: $(PACKAGE))"; exit 1;; esac
	$(CONTAINER_PYTHON) scripts/list-tags.py $(PACKAGE)

scaffold-package: check-image check-venv setup-volumes ## Scaffold a new packages.yaml entry from a submodule (PACKAGE=<name> required, single package only)
	@case "$(PACKAGE)" in *,*) echo "$(HIGHLIGHT_PREFIX) Error: PACKAGE must be a single package name here (got a comma-separated list: $(PACKAGE))"; exit 1;; esac
	$(CONTAINER_PYTHON) scripts/scaffold-package.py $(PACKAGE)
	$(MAKE) fmt

add-submodule: check-image check-venv setup-volumes ## Register git submodule for an existing package (PACKAGE=<name> required, single package only)
	@test -n "$(PACKAGE)" || (echo "$(HIGHLIGHT_PREFIX) Error: PACKAGE is required"; exit 1)
	@case "$(PACKAGE)" in *,*) echo "$(HIGHLIGHT_PREFIX) Error: PACKAGE must be a single package name here (got a comma-separated list: $(PACKAGE))"; exit 1;; esac
	@_url=$$($(CONTAINER_PYTHON) -c "import yaml; d=yaml.safe_load(open('packages.yaml')); print(d['$(PACKAGE)']['url'])" 2>&1) || \
		(echo "$(HIGHLIGHT_PREFIX) Error: Failed to read URL for $(PACKAGE) from packages.yaml"; exit 1); \
	 _name=$$(basename $$_url); \
	 _org=$$(basename $$(dirname $$_url)); \
	 echo $(HIGHLIGHT_PREFIX) "adding submodule submodules/$$_org/$$_name"; \
	 git submodule add $$_url submodules/$$_org/$$_name || exit 1; \
	 git config -f .gitmodules submodule.submodules/$$_org/$$_name.ignore dirty || exit 1; \
	 echo $(HIGHLIGHT_PREFIX) "✓ configured ignore=dirty for submodule"

add-new: check-image check-venv setup-volumes ## Add submodule from URL and scaffold packages.yaml entry in one step (URL=<repo-url> required)
	@test -n "$(URL)" || (echo "$(HIGHLIGHT_PREFIX) Error: URL is required (e.g. URL=https://github.com/hyprwm/hyprpicker)"; exit 1)
	@echo "$(URL)" | grep -qE '^https?://' || (echo "$(HIGHLIGHT_PREFIX) Error: URL must be http:// or https://, not git:// or other schemes"; exit 1)
	@_name=$$(basename $(URL:.git=)); \
	 _org=$$(basename $$(dirname $(URL))); \
	 git submodule add $(URL) submodules/$$_org/$$_name || exit 1; \
	 git config -f .gitmodules submodule.submodules/$$_org/$$_name.ignore dirty || exit 1; \
	 $(CONTAINER_PYTHON) scripts/scaffold-package.py $$_name || exit 1
	$(MAKE) fmt

delete-package: check-image check-venv setup-volumes ## Remove package from packages.yaml, groups.yaml, sources.lock.yaml, build-report.db, logs/runs/*/*/<name>, packages/, submodules, and container rpmbuild dirs (PKG=<name> or PACKAGE=<name> required, single package only)
	@test -n "$(PACKAGE)" || (echo "$(HIGHLIGHT_PREFIX) Error: PKG or PACKAGE is required (e.g. PKG=hyprpicker)"; exit 1)
	@case "$(PACKAGE)" in *,*) echo "$(HIGHLIGHT_PREFIX) Error: PACKAGE must be a single package name here (got a comma-separated list: $(PACKAGE))"; exit 1;; esac
	@echo "$(HIGHLIGHT_PREFIX) Removing package '$(PACKAGE)'..."
	@$(CONTAINER_PYTHON) scripts/delete-package.py $(PACKAGE)
	@rm -rf packages/$(PACKAGE)
	@_path=$$(git config -f .gitmodules --get-regexp '^submodule\.' | grep -E 'path\s' | grep '/$(PACKAGE)$$' | cut -d' ' -f2); \
	 if [ -n "$$_path" ]; then \
	   _sec=$$(git config -f .gitmodules --get-regexp '^submodule\.' | grep -E 'path\s' | grep '/$(PACKAGE)$$' | sed 's/submodule\.\(.*\)\.path.*/\1/'); \
	   if [ -n "$$_sec" ]; then \
	     git reset HEAD $$_path || exit 1; \
	     git config -f .gitmodules --remove-section submodule.$$_sec || exit 1; \
	     git add .gitmodules || exit 1; \
	     git rm --cached $$_path || exit 1; \
	     rm -rf $$_path .git/modules/$$_path || exit 1; \
	     echo "$(HIGHLIGHT_PREFIX) Removed git submodule: $$_path"; \
	   fi; \
	 fi
	@if $(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(RPMBUILD_VOLUME) >/dev/null 2>&1; then \
	  $(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run --rm -v $(RPMBUILD_MOUNT) $(IMAGE_NAME) \
	    rm -rf /root/rpmbuild/SOURCES/$(PACKAGE)-* /root/rpmbuild/SRPMS/$(PACKAGE)-* /root/rpmbuild/RPMS/*/$(PACKAGE)-* || exit 1; \
	fi
	@echo "$(HIGHLIGHT_PREFIX) ✓ Removed $(PACKAGE)"

set-release: check-image check-venv setup-volumes ## Set package release value (PACKAGE=<name|name1,name2,...> RELEASE=<num> required; LOCK=1 to prevent auto-increment)
	@test -n "$(PACKAGE)" || (echo "$(HIGHLIGHT_PREFIX) Error: PACKAGE is required (e.g. PACKAGE=hyprlang or PACKAGE=hyprlang,hyprutils)"; exit 1)
	@test -n "$(RELEASE)" || (echo "$(HIGHLIGHT_PREFIX) Error: RELEASE is required (e.g. RELEASE=5)"; exit 1)
	$(CONTAINER_PYTHON) scripts/set-package-release.py $(PACKAGE) $(RELEASE) $(if $(filter 1,$(LOCK)),--lock,)

gather-requires: check-image check-venv setup-volumes ## Suggest requires entries from built RPMs (RPM=path/to/pkg.rpm [path/to/other.rpm ...] required -- a filesystem path, not a packages.yaml name)
	@test -n "$(RPM)" || (echo "$(HIGHLIGHT_PREFIX) Error: RPM is required (e.g. RPM=local-repo/fedora-44-x86_64/hyprutils-0.14.0.fc44.x86_64.rpm)"; exit 1)
	$(CONTAINER_PYTHON) scripts/gather-requires.py $(RPM)

gen-report: check-image check-venv setup-volumes ## Render build-report.db to stdout for FEDORA_VERSION (--format github|copr)
	$(CONTAINER_RUN) env FEDORA_VERSION=$(FEDORA_VERSION) MOCK_CHROOT=$(MOCK_CHROOT) \
		/work/.venv/bin/python3 scripts/gen-report.py $(if $(FORMAT),--format $(FORMAT),)

readme: check-image check-venv setup-volumes ## Generate README.md, docs/README.copr.md, and docs/full-report.md for FEDORA_VERSION
	@mkdir -p "$(MAKE_LOGS_DIR)/readme"
	@$(CONTAINER_RUN) env FEDORA_VERSION=$(FEDORA_VERSION) MOCK_CHROOT=$(MOCK_CHROOT) \
		/work/.venv/bin/python3 scripts/gen-report.py \
			--format github      --output ./README.md \
			--format copr        --output ./docs/README.copr.md \
			--format full-report --output ./docs/full-report.md \
		2>"$(MAKE_LOGS_DIR)/readme/render.log" || (echo "$(HIGHLIGHT_PREFIX) ✗ README/docs generation failed"; exit 1)
	@echo "$(HIGHLIGHT_PREFIX) ✓ GitHub README generated"
	@echo "$(HIGHLIGHT_PREFIX) ✓ COPR README generated"
	@echo "$(HIGHLIGHT_PREFIX) ✓ Full Report generated"

readme-shell: check-image check-venv ## Regenerate only the branding shell of README.md/docs/README.copr.md (no build-report.db needed; for CI)
	$(call run_with_result,$(CONTAINER_PYTHON) scripts/gen-readme-shell.py,Readme shell updated,Readme shell update failed)

db-usage: check-image check-venv setup-volumes ## Report disk usage of tracked build artifacts by package/target. VERIFY=1 also re-hashes every artifact to flag corruption
	@$(CONTAINER_PYTHON) scripts/db-artifacts.py --usage $(if $(filter 1,$(VERIFY)),--verify,)

db-prune: check-image check-venv setup-volumes ## Remove all but the newest artifact per (package,target,kind). Dry-run by default; CONFIRM=1 to actually delete
	@$(CONTAINER_PYTHON) scripts/db-artifacts.py --prune $(if $(filter 1,$(CONFIRM)),--confirm,)

db-export: check-image check-venv setup-volumes ## Snapshot runs/stage_results/stage_history/artifacts for offline diffing. FORMAT=yaml|json (default yaml), OUTPUT=path (default stdout)
	@$(CONTAINER_PYTHON) scripts/db-artifacts.py --export \
		$(if $(FORMAT),--format $(FORMAT),) $(if $(OUTPUT),--output $(OUTPUT),)

db-shell: check-image check-venv ## Open an interactive sqlite3 shell on build-report.db. NO_CONTAINER=1 opens it directly on the host (#BUG-0062)
ifeq ($(NO_CONTAINER),1)
	@.venv/bin/python3 -m sqlite3 build-report.db
else
	@$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run -it --rm \
		-v $(WORKDIR_MOUNT) \
		-v $(VENV_MOUNT) \
		-w /work \
		$(IMAGE_NAME) /work/.venv/bin/python3 -m sqlite3 build-report.db
endif

db-nuke: ## DESTROY build-report.db entirely: artifact ledger + all run/stage history (irreversible; confirmation required)
	@printf "$(HIGHLIGHT_PREFIX) Destroy build-report.db entirely (artifact ledger + all history)? [y/N] "; \
	read ans; \
	[ "$$ans" = "y" ] || [ "$$ans" = "Y" ] || { echo "$(HIGHLIGHT_PREFIX) Aborted."; exit 1; }
	@rm -f build-report.db build-report.db-wal build-report.db-shm
	@echo $(HIGHLIGHT_PREFIX) "✓ build-report.db destroyed"

# Update the COPR project description and instructions from markdown files.
# Requires: copr-cli installed + ~/.config/copr token
copr-description: check-image setup-volumes ## Push description and install instructions to COPR (COPR_REPO required)
	@test -n "$(COPR_REPO)" || (echo "$(HIGHLIGHT_PREFIX) Error: COPR_REPO is not set (e.g. export COPR_REPO=nett00n/hyprland)"; exit 1)
	@test -f "$(README_COPR)" || (echo "$(HIGHLIGHT_PREFIX) Error: $(README_COPR) not found"; exit 1)
	@test -f "$(COPR_INSTRUCTIONS)" || (echo "$(HIGHLIGHT_PREFIX) Warning: $(COPR_INSTRUCTIONS) not found, skipping instructions"; true)
	$(CONTAINER_RUN) copr-cli modify "$(COPR_REPO)" \
		--description "$$(cat $(README_COPR))" \
		$(if $(shell test -f "$(COPR_INSTRUCTIONS)" && echo 1),--instructions "$$(cat $(COPR_INSTRUCTIONS))",)
	@echo $(HIGHLIGHT_PREFIX) "✓ Description updated → $(COPR_REPO)"

normalize-paths: check-image check-venv setup-volumes ## Normalize paths in packages.yaml abs->macros (ARGS=--reverse or --dry-run)
	$(CONTAINER_PYTHON) scripts/rpm-dir-prefixes-convert.py $(ARGS)

sort-lists: check-image check-venv setup-volumes ## Sort build_requires/requires/files lists in packages.yaml (ARGS=--dry-run)
	$(CONTAINER_PYTHON) scripts/sort-yaml-lists.py $(ARGS)

container-build: ## Build the single container image (builds every SUPPORTED chroot via `mock -r`; version-independent, no FEDORA_VERSION build-arg)
	$(call run_with_result,$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) build \
		--build-arg UID=$(USER_ID) \
		--build-arg GID=$(GROUP_ID) \
		-t $(IMAGE_NAME) \
		-f Containerfile .,Built $(IMAGE_NAME),Container build failed)

container-enter: check-image check-venv setup-volumes ## Enter interactive shell in the container
	$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run -it --rm --privileged \
		$(CONTAINER_MOUNTS) \
		-w /work \
		$(IMAGE_NAME) /bin/bash

container-clean: ## Remove the container image
	$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) image inspect $(IMAGE_NAME) >/dev/null 2>&1 && \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) rmi $(IMAGE_NAME) || true
	@echo $(HIGHLIGHT_PREFIX) "Cleaned $(IMAGE_NAME)"

container-volume-clean: ## Remove volumes: rpmbuild (shared, once) and mock-cache/mock-root (per FEDORA_VERSION; all SUPPORTED if not specified); local-repo/ itself is a plain directory now, remove by hand if wanted
	@if [ "$(FEDORA_VERSION)" = "44" ] && [ -z "$(RECURSIVE_CALL)" ]; then \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(RPMBUILD_VOLUME) >/dev/null 2>&1 && \
			$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume rm $(RPMBUILD_VOLUME) || true; \
		for v in $(SUPPORTED); do \
			echo $(HIGHLIGHT_PREFIX) "Removing mock volumes for Fedora $$v..."; \
			$(MAKE) container-volume-clean FEDORA_VERSION=$$v RECURSIVE_CALL=1 || exit 1; \
		done; \
		echo $(HIGHLIGHT_PREFIX) "All volumes cleaned"; \
	else \
		echo $(HIGHLIGHT_PREFIX) "Removing mock volumes for Fedora $(FEDORA_VERSION)..."; \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(MOCKCACHE_VOLUME) >/dev/null 2>&1 && \
			$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume rm $(MOCKCACHE_VOLUME) || true; \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(MOCKROOT_VOLUME) >/dev/null 2>&1 && \
			$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume rm $(MOCKROOT_VOLUME) || true; \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(LOCALREPO_VOLUME) >/dev/null 2>&1 && \
			$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume rm $(LOCALREPO_VOLUME) || true; \
		echo $(HIGHLIGHT_PREFIX) "Cleaned volumes: $(MOCKCACHE_VOLUME), $(MOCKROOT_VOLUME)"; \
	fi

container-all: ## Alias for container-build -- kept for scripts/docs that still call it; one image now covers every SUPPORTED chroot
	@$(MAKE) container-build

sources: check-image check-venv setup-volumes ## Download sources for PACKAGE (or all) using spectool, then verify against sources.lock.yaml (runs in container)
	@for pkg in $(_PKGS); do \
		_spec="packages/$$pkg/$$pkg.spec"; \
		if [ ! -f "$$_spec" ]; then \
			echo "$(HIGHLIGHT_PREFIX) ✗ sources: $$pkg - spec file not found: $$_spec"; exit 1; \
		fi; \
	done
	@$(CONTAINER_RUN) sh -c 'set -e; for pkg in $(_PKGS); do \
		echo "$(HIGHLIGHT_PREFIX) sources: $$pkg"; \
		spectool -g -R "packages/$$pkg/$$pkg.spec"; \
	done'
	$(MAKE) check-checksums PACKAGE=$(PACKAGE)

FORCE_REBUILD ?=
PROCEED_BUILD ?=
SKIP_MOCK ?=
SKIP_COPR ?=
SKIP_RELEASE_BUMP ?=
SYNCHRONOUS_COPR_BUILD ?=
REQUIRE_CHROOT_COVERAGE ?=

full-cycle: ## Run full cycle with YAML report: spec → srpm → mock → copr (PACKAGE, COPR_REPO, FORCE_REBUILD, env vars)
	@mkdir -p logs
	@if [ "$(PIPELINE_LOCK_HELD)" = "1" ] || [ "$(LOCK_DISABLE)" = "1" ]; then \
		$(MAKE) _full-cycle; \
	elif ! command -v flock >/dev/null 2>&1; then \
		echo $(HIGHLIGHT_PREFIX) "Error: flock not found (util-linux); install it, or bypass with LOCK_DISABLE=1"; \
		exit 1; \
	else \
		exec 9>$(PIPELINE_LOCK_FILE); \
		flock -n 9 || { \
			echo $(HIGHLIGHT_PREFIX) "Error: another pipeline run is already in progress ($$(cat $(PIPELINE_LOCK_FILE).owner 2>/dev/null || echo 'holder unknown')) -- refusing to run concurrently"; \
			exit 1; \
		}; \
		echo "PID $$$$, started $$(date --rfc-3339=seconds), target _full-cycle" > $(PIPELINE_LOCK_FILE).owner; \
		PIPELINE_LOCK_HELD=1 $(MAKE) _full-cycle; \
	fi

_full-cycle: check-image check-venv setup-volumes
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		COPR_REPO=$(COPR_REPO) \
		FORCE_REBUILD=$(FORCE_REBUILD) \
		SKIP_PACKAGES=$(SKIP_PACKAGES) \
		PROCEED_BUILD=$(PROCEED_BUILD) \
		SKIP_MOCK=$(SKIP_MOCK) \
		SKIP_COPR=$(SKIP_COPR) \
		SKIP_RELEASE_BUMP=$(SKIP_RELEASE_BUMP) \
		SYNCHRONOUS_COPR_BUILD=$(SYNCHRONOUS_COPR_BUILD) \
		REQUIRE_CHROOT_COVERAGE=$(REQUIRE_CHROOT_COVERAGE) \
		$(if $(SKIP_REPO_PREFLIGHT),SKIP_REPO_PREFLIGHT=$(SKIP_REPO_PREFLIGHT),) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/full-cycle.py,Full cycle completed,Full cycle failed)

MATRIX_VERSIONS ?= $(SUPPORTED)
# The canonical chroot performs the release auto-increment (SKIP_RELEASE_BUMP,
# docs/BUGS.md BUG-0049) -- every other chroot in this run must build after
# it, or it could cache its spec/SRPM against the pre-bump release and never
# regenerate. Enforced by building this list in order, NOT by a Make
# prerequisite: an order-only prereq plus `make -k` silently SKIPS every
# dependent chroot whenever the canonical one's recipe fails ("Target
# 'matrix-chroot-44' not remade because of errors" -- documented -k
# behaviour), which starved fedora-44 and fedora-45 of every nightly run for
# as long as one package failed on fedora-43 (docs/BUGS.md BUG-0053).
# $(filter) is a no-op when the caller's MATRIX_VERSIONS excludes the
# canonical version -- no release bump happens that run at all then
# (docs/operations.md), so there is nothing to order.
MATRIX_ORDERED_VERSIONS := $(filter $(CANONICAL_FEDORA_VERSION),$(MATRIX_VERSIONS)) \
                           $(filter-out $(CANONICAL_FEDORA_VERSION),$(MATRIX_VERSIONS))

# Deliberately NOT declared .PHONY: doing so makes GNU Make treat the target
# as already having an explicit rule and stop searching for this pattern rule
# to supply a recipe -- reproduced in isolation, not a Makefile-specific bug.
# These targets never correspond to a real file, so they already rebuild
# unconditionally without .PHONY.
matrix-chroot-%: ## Build one Fedora chroot via full-cycle. Normally driven by full-cycle-matrix's loop; safe to invoke by hand (e.g. `make matrix-chroot-45`) to backfill one chroot's coverage. Standalone, it does NOT run the canonical chroot first, so it never bumps releases unless % is the canonical version.
	@echo $(HIGHLIGHT_PREFIX) "Fedora $*"
	@if [ "$*" = "$(CANONICAL_FEDORA_VERSION)" ]; then bump=; else bump=true; fi; \
	$(MAKE) full-cycle FEDORA_VERSION=$* PACKAGE=$(PACKAGE) SKIP_COPR=true \
		SKIP_PACKAGES=$(SKIP_PACKAGES) FORCE_REBUILD=$(FORCE_REBUILD) \
		SKIP_RELEASE_BUMP=$$bump

full-cycle-matrix: ## Build every MATRIX_VERSIONS chroot locally (default: all SUPPORTED, x86_64 only; a failing chroot doesn't stop the rest), then submit to Copr once for packages that built cleanly everywhere (PACKAGE, COPR_REPO, requires 'make container-build' first)
	@mkdir -p logs
	@if [ "$(PIPELINE_LOCK_HELD)" = "1" ] || [ "$(LOCK_DISABLE)" = "1" ]; then \
		$(MAKE) _full-cycle-matrix; \
	elif ! command -v flock >/dev/null 2>&1; then \
		echo $(HIGHLIGHT_PREFIX) "Error: flock not found (util-linux); install it, or bypass with LOCK_DISABLE=1"; \
		exit 1; \
	else \
		exec 9>$(PIPELINE_LOCK_FILE); \
		flock -n 9 || { \
			echo $(HIGHLIGHT_PREFIX) "Error: another pipeline run is already in progress ($$(cat $(PIPELINE_LOCK_FILE).owner 2>/dev/null || echo 'holder unknown')) -- refusing to run concurrently"; \
			exit 1; \
		}; \
		echo "PID $$$$, started $$(date --rfc-3339=seconds), target _full-cycle-matrix" > $(PIPELINE_LOCK_FILE).owner; \
		PIPELINE_LOCK_HELD=1 $(MAKE) _full-cycle-matrix; \
	fi

# One chroot's failure must never prevent another chroot from being attempted
# (docs/BUGS.md BUG-0053) -- an explicit `|| overall=1` loop, not `make -k`,
# because -k refuses to attempt any target ordered after a failed one.
# stage-copr's own exit status is folded into `overall` too, so a failed
# submission is no longer invisible to update-daily's
# `|| touch logs/.update-daily-failed` gate (docs/BUGS.md BUG-0050).
_full-cycle-matrix:
	@overall=0; failed_chroots=; \
	for v in $(MATRIX_ORDERED_VERSIONS); do \
		$(MAKE) matrix-chroot-$$v || { overall=1; failed_chroots="$$failed_chroots $$v"; }; \
	done; \
	if [ -n "$$failed_chroots" ]; then \
		echo $(HIGHLIGHT_PREFIX) "✗ chroot(s) with build failures:$$failed_chroots (other chroots and Copr submission still ran)"; \
	fi; \
	if [ -n "$(COPR_REPO)" ]; then \
		$(MAKE) stage-copr FEDORA_VERSION=$(FEDORA_VERSION) PACKAGE=$(PACKAGE) COPR_REPO=$(COPR_REPO) \
			REQUIRE_CHROOT_COVERAGE=$(REQUIRE_CHROOT_COVERAGE) || overall=1; \
	else \
		echo $(HIGHLIGHT_PREFIX) "COPR_REPO not set -- skipping Copr submission (local matrix build only)"; \
	fi; \
	exit $$overall

update-daily: ## Update versions, validate+format packages.yaml, build (package failures reported but don't block docs/commit), generate docs, push to COPR (requires COPR_REPO), git commit (PUSH=1 to also git push)
	@mkdir -p logs
	@if [ "$(PIPELINE_LOCK_HELD)" = "1" ] || [ "$(LOCK_DISABLE)" = "1" ]; then \
		$(MAKE) _update-daily; \
	elif ! command -v flock >/dev/null 2>&1; then \
		echo $(HIGHLIGHT_PREFIX) "Error: flock not found (util-linux); install it, or bypass with LOCK_DISABLE=1"; \
		exit 1; \
	else \
		exec 9>$(PIPELINE_LOCK_FILE); \
		flock -n 9 || { \
			echo $(HIGHLIGHT_PREFIX) "Error: another pipeline run is already in progress ($$(cat $(PIPELINE_LOCK_FILE).owner 2>/dev/null || echo 'holder unknown')) -- refusing to run concurrently"; \
			exit 1; \
		}; \
		echo "PID $$$$, started $$(date --rfc-3339=seconds), target _update-daily" > $(PIPELINE_LOCK_FILE).owner; \
		PIPELINE_LOCK_HELD=1 $(MAKE) _update-daily; \
	fi

_update-daily:
	@test -n "$(COPR_REPO)" || (echo "$(HIGHLIGHT_PREFIX) Error: COPR_REPO is not set (e.g. export COPR_REPO=nett00n/hyprland)"; exit 1)
	@mkdir -p logs && rm -f logs/.update-daily-failed
	$(MAKE) update-versions || exit 1
	$(MAKE) validate-packages fmt || exit 1
	$(MAKE) refresh-checksums || exit 1
	$(MAKE) full-cycle-matrix || touch logs/.update-daily-failed
	@# full-cycle.py's update_package_releases() rewrites packages.yaml after the
	@# pre-build gate ran, so re-validate the file that actually gets committed and
	@# rendered into the docs below (docs/BUGS.md BUG-0044). No re-fmt: the rewrite
	@# already goes through write_yaml_file's FORMAT_FILE, same as format-yaml.py.
	$(MAKE) validate-packages || exit 1
	$(MAKE) readme copr-description || exit 1
	@# stage-log-analyze runs here, after readme's gen-report.py has polled Copr and
	@# fetched any newly-failed chroot logs (see lib.copr.poll_copr_status), and
	@# writes docs/nightly-summary.md (#COPR-0022) -- each run's logs live under
	@# their own logs/runs/<run_id>/ (see lib.paths.get_run_log_dir), pruned by
	@# retention policy rather than destroyed at the start of the next run, so
	@# there's no ordering constraint against a future run's log setup any more
	@# (formerly BUG-0041). pkg-log-analysis.py exits non-zero when it finds
	@# issues (not an error), so this must not abort the recipe.
	$(MAKE) stage-log-analyze LOG_SUMMARY_OUTPUT=docs/nightly-summary.md || true
	git add packages.yaml packages/ submodules/ sources.lock.yaml README.md docs/README.copr.md docs/full-report.md || exit 1
	@[ -f docs/nightly-summary.md ] && git add docs/nightly-summary.md || true
	@if git diff --cached --quiet; then \
		echo "$(HIGHLIGHT_PREFIX) Nothing to commit (no version/doc changes tonight)."; \
	else \
		git commit -m "Daily update: $$(date --rfc-3339=seconds)" || exit 1; \
		if [ "$(PUSH)" = "1" ]; then \
			git pull --rebase origin main || exit 1; \
			git push || exit 1; \
		fi; \
	fi
	@echo $(HIGHLIGHT_PREFIX) "$$(cat logs/.update-versions-count 2>/dev/null || echo '?') package(s) updated tonight"
	@if [ -f logs/.update-versions-failures.md ]; then \
		echo "$(HIGHLIGHT_PREFIX) ✗ $$(grep -c '^- \`' logs/.update-versions-failures.md 2>/dev/null || echo '?') upstream refresh failure(s) tonight (see docs/nightly-summary.md's Upstream version refresh section, or logs/.update-versions-failures.md) #BUG-0100"; \
	fi
	@if [ -f logs/.update-daily-failed ]; then \
		rm -f logs/.update-daily-failed; \
		echo "$(HIGHLIGHT_PREFIX) ✗ Some packages failed to build tonight (docs and commit were still produced; see stage-log-analyze output above, docs/nightly-summary.md, or logs/runs/latest/<target>/<pkg>)"; \
		exit 1; \
	fi

build-pop: check-image check-venv setup-volumes ## Remove mock/copr build status for PKG=a,b (PKG="" removes all, requires confirmation)
	@if [ -z "$(PACKAGE)" ]; then \
		printf "$(HIGHLIGHT_PREFIX) Remove mock/copr status for ALL packages? [y/N] "; \
		read ans; \
		[ "$$ans" = "y" ] || [ "$$ans" = "Y" ] || { echo "$(HIGHLIGHT_PREFIX) Aborted."; exit 1; }; \
	fi
	@$(CONTAINER_RUN) env FEDORA_VERSION=$(FEDORA_VERSION) MOCK_CHROOT=$(MOCK_CHROOT) PACKAGE=$(PACKAGE) \
		/work/.venv/bin/python3 scripts/pkg-build-pop.py || exit 1

stage-validate: check-image check-venv setup-volumes ## Run validation stage (PACKAGE=<name>, PROCEED_BUILD, CMD_TIMEOUT, runs in container)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		PROCEED_BUILD=$(PROCEED_BUILD) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/stage-validate.py,Validation stage passed,Validation stage failed)

stage-show-plan: check-image check-venv setup-volumes ## Show build plan - what will run, cache, or skip (PACKAGE, SKIP_PACKAGES, COPR_REPO, FORCE_REBUILD optional, runs in container)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		SKIP_PACKAGES=$(SKIP_PACKAGES) \
		COPR_REPO=$(COPR_REPO) \
		FORCE_REBUILD=$(FORCE_REBUILD) \
		/work/.venv/bin/python3 scripts/stage-show-plan.py,Build plan displayed,Build plan failed)

stage-spec: check-image check-venv setup-volumes ## Run spec generation stage (PACKAGE=<name>, MOCK_CHROOT, PROCEED_BUILD, CMD_TIMEOUT, runs in container)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		PROCEED_BUILD=$(PROCEED_BUILD) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/stage-spec.py,Spec generation passed,Spec generation failed)

stage-vendor: check-image check-venv setup-volumes ## Run vendor tarball generation stage (Go/Rust packages, PACKAGE=<name>, MOCK_CHROOT, SKIP_PACKAGES, PROCEED_BUILD, CMD_TIMEOUT, runs in container)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		SKIP_PACKAGES=$(SKIP_PACKAGES) \
		PROCEED_BUILD=$(PROCEED_BUILD) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/stage-vendor.py,Vendor stage passed,Vendor stage failed)

FORCE_CHECKSUM ?=

refresh-checksums: check-image check-venv setup-volumes ## Download+pin sha256 for remote sources into sources.lock.yaml (PACKAGE, SKIP_PACKAGES, FORCE_CHECKSUM, CMD_TIMEOUT)
	$(call run_with_result,$(CONTAINER_RUN) env \
		PACKAGE=$(PACKAGE) \
		SKIP_PACKAGES=$(SKIP_PACKAGES) \
		FORCE_CHECKSUM=$(FORCE_CHECKSUM) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/refresh-checksums.py,Checksums refreshed,Checksum refresh failed)

check-checksums: check-image check-venv setup-volumes ## Verify downloaded sources against sources.lock.yaml, no download/write (PACKAGE, SKIP_PACKAGES)
	$(call run_with_result,$(CONTAINER_RUN) env \
		PACKAGE=$(PACKAGE) \
		SKIP_PACKAGES=$(SKIP_PACKAGES) \
		/work/.venv/bin/python3 scripts/refresh-checksums.py --check,Checksums verified,Checksum verification failed)

stage-srpm: check-image check-venv setup-volumes ## Run SRPM build stage (PACKAGE=<name>, MOCK_CHROOT, PROCEED_BUILD, CMD_TIMEOUT, runs in container)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		PROCEED_BUILD=$(PROCEED_BUILD) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/stage-srpm.py,SRPM stage passed,SRPM stage failed)

stage-mock: check-image check-venv setup-volumes ## Run mock build stage (PACKAGE=<name>, FEDORA_VERSION, PROCEED_BUILD, CMD_TIMEOUT, SKIP_REPO_PREFLIGHT=1 to demote the local-repo preflight to warnings, runs in container)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		PROCEED_BUILD=$(PROCEED_BUILD) \
		$(if $(SKIP_REPO_PREFLIGHT),SKIP_REPO_PREFLIGHT=$(SKIP_REPO_PREFLIGHT),) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/stage-mock.py,Mock build stage passed,Mock build stage failed)

stage-copr: check-image check-venv setup-volumes ## Run Copr submission stage (PACKAGE=<name>, COPR_REPO required, MOCK_CHROOT, REQUIRE_CHROOT_COVERAGE, PROCEED_BUILD, CMD_TIMEOUT, runs in container)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		COPR_REPO=$(COPR_REPO) \
		REQUIRE_CHROOT_COVERAGE=$(REQUIRE_CHROOT_COVERAGE) \
		PROCEED_BUILD=$(PROCEED_BUILD) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/stage-copr.py,Copr submission stage passed,Copr submission stage failed)

_LOG_PKGS := $(filter-out $(subst $(comma),$(space),$(SKIP_PACKAGES)),$(_PKGS))

stage-log-analyze: check-image check-venv setup-volumes ## Analyze build logs for packages and report actionable errors (PACKAGE=<name> for one, runs for all by default, respects SKIP_PACKAGES). LOG_SUMMARY_OUTPUT=<path> also writes a durable Markdown summary there (#COPR-0022)
	@$(CONTAINER_PYTHON) scripts/pkg-log-analysis.py $(_LOG_PKGS) $(if $(LOG_SUMMARY_OUTPUT),--output $(LOG_SUMMARY_OUTPUT),)

prune-logs: check-image check-venv ## Enforce log retention on logs/runs/ (#COPR-0022). Dry-run by default; CONFIRM=1 to delete. KEEP=<n> overrides LOG_RETENTION_RUNS (default 10)
	@$(CONTAINER_PYTHON) scripts/prune-logs.py $(if $(KEEP),--keep $(KEEP),) $(if $(filter 1,$(CONFIRM)),--confirm,)

# HM_HOME points at the HyperMnesia checkout (#COPR-0024); runs on the host, never in the
# container, since it talks to an external Postgres over $(DATABASE_URL).
HM_HOME       ?= $(HOME)/personal-env/hypermnesia
HM_SCOPE      ?= hyprland-copr-daily

memory-refresh: ## Re-ingest docs/ into HyperMnesia and check the store is healthy (#COPR-0024). No-op if DATABASE_URL is unset -- see docs/features/COPR-0024-hypermnesia-memory.md
	@if [ -z "$(DATABASE_URL)" ]; then \
		echo "memory-refresh: DATABASE_URL not set, skipping (HyperMnesia not configured on this box)"; \
	elif [ ! -d "$(HM_HOME)" ]; then \
		echo "memory-refresh: $(HM_HOME) not found, skipping"; \
	else \
		cd "$(HM_HOME)" && HM_PYTHON=$(HM_HOME)/.venv/bin/python3 HM_REPO=$(HM_SCOPE) ./hm ingest $(CURDIR) $(HM_SCOPE) && \
		.venv/bin/python ci/freshness.py $(CURDIR) $(HM_SCOPE) && \
		HM_PYTHON=$(HM_HOME)/.venv/bin/python3 HM_REPO=$(HM_SCOPE) ./hm doctor; \
	fi
