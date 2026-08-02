# Load .env file if it exists (allows declaring defaults without overriding env exports)
-include .env
# Strip quotes from .env variables (shell syntax vs make syntax)
FEDORA_VERSION  := $(subst ",,$(FEDORA_VERSION))
COPR_REPO       := $(subst ",,$(COPR_REPO))
PACKAGE         := $(subst ",,$(PACKAGE))
SKIP_PACKAGES   := $(subst ",,$(SKIP_PACKAGES))
# Fallback defaults if not set after stripping
FEDORA_VERSION  ?= 43
SUPPORTED        := 43 44 rawhide
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

ifeq ($(FEDORA_VERSION),rawhide)
  MOCK_CHROOT := fedora-rawhide-x86_64
else
  MOCK_CHROOT := fedora-$(FEDORA_VERSION)-x86_64
endif

# Container runtime: podman (default) or docker (fallback)
CONTAINER_RUNTIME ?= $(shell command -v podman >/dev/null 2>&1 && echo podman || echo docker)
CONTAINER_SUDO    := $(if $(filter docker,$(CONTAINER_RUNTIME)),sudo,)

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

# Per-Fedora-version volumes (container user is set in Containerfile)
RPMBUILD_VOLUME  := rpmbuild-$(FEDORA_VERSION)
RPMBUILD_MOUNT   := $(RPMBUILD_VOLUME):/root/rpmbuild:z
LOCALREPO_VOLUME := local-repo-$(FEDORA_VERSION)
LOCALREPO_MOUNT  := $(LOCALREPO_VOLUME):/local-repo:z
WORKDIR_MOUNT    := $(PWD):/work:z
VENV_MOUNT       := $(PWD)/.venv:/work/.venv:z
MOCK_CONF_MOUNT  := $(PWD)/mock-local-repo.conf:/etc/mock/local-repo.conf:ro,z
COPR_MOUNT_OPT   := ro,z
COPR_CONFIG_MOUNT := $(if $(COPR_REPO),-v $(HOME_DIR)/.config/copr:/root/.config/copr:$(COPR_MOUNT_OPT),)


# Container execution with volume mounts
# Note: Containerfile already sets USER, so don't override it here
# --privileged flag is required for mock to work (namespace support)
ifeq ($(NO_CONTAINER),1)
CONTAINER_RUN    :=
CONTAINER_PYTHON := .venv/bin/python3
RPMLINT          := .venv/bin/rpmlint
WORK             := .
else
CONTAINER_RUN := $(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run --rm --privileged \
	-v $(RPMBUILD_MOUNT) \
	-v $(LOCALREPO_MOUNT) \
	-v $(WORKDIR_MOUNT) \
	-v $(VENV_MOUNT) \
	-v $(MOCK_CONF_MOUNT) \
	$(COPR_CONFIG_MOUNT) \
	$(if $(LOG_LEVEL),-e LOG_LEVEL=$(LOG_LEVEL),) \
	-w /work \
	$(IMAGE_NAME):$(FEDORA_VERSION)

# Python in container using mounted .venv
CONTAINER_PYTHON := $(CONTAINER_RUN) /work/.venv/bin/python3
RPMLINT          := rpmlint
WORK             := /work
endif

ALL_PACKAGES := $(shell grep -oP '^[a-zA-Z][a-zA-Z0-9_-]+(?=:)' packages.yaml)
_PKGS        := $(if $(PACKAGE),$(PACKAGE),$(ALL_PACKAGES))

PYTHON           := .venv/bin/python3
README_COPR      := docs/README.copr.md
COPR_INSTRUCTIONS := docs/INSTALL.copr.md

# Helper: run command, echo success/failure
# Usage: $(call run_with_result,command,success_msg,fail_msg)
define run_with_result
	@$1 && echo $(HIGHLIGHT_PREFIX) "✓ $2" || (echo $(HIGHLIGHT_PREFIX) "✗ $3"; exit 1)
endef


.DEFAULT_GOAL := help
.PHONY: help setup-venv setup-volumes test coverage lint lint-ruff lint-flake lint-mypy lint-yaml lint-rpm fmt fmt-ruff fmt-yaml pre-commit update-versions list-tags scaffold-package add-submodule add-new delete-package set-release gather-requires gen-report readme readme-shell copr-description normalize-paths sort-lists container-build container-enter container-clean container-volume-clean container-all sources full-cycle full-cycle-matrix update-daily build-pop stage-validate stage-show-plan stage-spec stage-vendor stage-srpm stage-mock stage-copr stage-log-analyze check-image check-venv save-last-build clean clean-logs clean-localrepo clean-all db-usage db-prune db-shell db-nuke

save-last-build: ## Save last built RPMs and build-report.db to local-repo/ before clean
	@mkdir -p local-repo
	@$(CONTAINER_RUN) sh -c "cp -r /local-repo/. /work/local-repo/"
	@[ -f build-report.db ] && cp build-report.db local-repo/build-report.db || true
	@echo $(HIGHLIGHT_PREFIX) "✓ Saved last build snapshot to local-repo/"

clean-logs: check-image check-venv setup-volumes ## Remove build logs; clears stage/run state but keeps the artifact ledger (use db-nuke to also drop that)
	@rm -rf logs/build logs/make
	@[ -f build-report.db ] && $(CONTAINER_PYTHON) scripts/db-artifacts.py --reset || true
	@echo $(HIGHLIGHT_PREFIX) "✓ Cleaned build logs and stage state (artifact ledger preserved)"

clean-localrepo: ## Purge local repo for FEDORA_VERSION to resolve dependency conflicts
	@$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(LOCALREPO_VOLUME) >/dev/null 2>&1 && \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run --rm -v $(LOCALREPO_MOUNT) $(IMAGE_NAME):$(FEDORA_VERSION) \
			rm -rf /local-repo/* || true
	@echo $(HIGHLIGHT_PREFIX) "✓ Cleaned local repo: $(LOCALREPO_VOLUME)"

clean-all: clean-logs clean-localrepo ## Clean logs and local repo; build-report.db's artifact ledger survives (see db-nuke)
	@echo $(HIGHLIGHT_PREFIX) "✓ Full cleanup completed"

clean: save-last-build clean-logs ## Remove build logs (saves last build first)

# Prerequisite checks - fail fast on missing dependencies
check-image: ## Verify container image exists for FEDORA_VERSION (no-op under NO_CONTAINER=1)
ifeq ($(NO_CONTAINER),1)
	@true
else
	@$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) image inspect $(IMAGE_NAME):$(FEDORA_VERSION) >/dev/null 2>&1 || \
		(echo "$(HIGHLIGHT_PREFIX) ✗ Container image not found: $(IMAGE_NAME):$(FEDORA_VERSION)"; \
		 echo "$(HIGHLIGHT_PREFIX) Run: make container-build FEDORA_VERSION=$(FEDORA_VERSION)"; exit 1)
endif

check-venv: ## Verify .venv exists and has Python
	@test -x .venv/bin/python3 || \
		(echo "$(HIGHLIGHT_PREFIX) ✗ Python venv not found or broken: .venv/bin/python3"; \
		 echo "$(HIGHLIGHT_PREFIX) Run: make setup-venv"; exit 1)

# Setup container volumes with correct permissions - required for rpmbuild and repo operations
setup-volumes: check-image ## Initialize rpmbuild and local-repo volumes with correct UID/GID (no-op under NO_CONTAINER=1)
ifeq ($(NO_CONTAINER),1)
	@true
else
	@$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(RPMBUILD_VOLUME) >/dev/null 2>&1 || \
		($(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume create $(RPMBUILD_VOLUME) || exit 1; \
		 $(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run --rm -v $(RPMBUILD_MOUNT) $(IMAGE_NAME):$(FEDORA_VERSION) \
		 	chown -R $(USER_ID):$(GROUP_ID) /root/rpmbuild || exit 1)
	@$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(LOCALREPO_VOLUME) >/dev/null 2>&1 || \
		($(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume create $(LOCALREPO_VOLUME) || exit 1; \
		 $(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run --rm -v $(LOCALREPO_MOUNT) $(IMAGE_NAME):$(FEDORA_VERSION) \
		 	chown -R $(USER_ID):$(GROUP_ID) /local-repo || exit 1)
	@echo "$(HIGHLIGHT_PREFIX) ✓ Volumes ready"
endif

help: ## Show this help
	@echo "Usage: make [TARGET] [PACKAGE=<name>] [FEDORA_VERSION=<version>] [LOG_LEVEL=<level>] [CMD_TIMEOUT=<seconds>]"
	@echo ""
	@echo "  Supported versions : $(SUPPORTED)"
	@echo "  Default version    : 43"
	@echo "  Default LOG_LEVEL  : INFO"
	@echo "  Default CMD_TIMEOUT: 3600 (60 minutes)"
	@echo ""
	@echo "  Common workflows:"
	@echo "    make sources PACKAGE=hyprland"
	@echo "    make stage-spec PACKAGE=hyprland"
	@echo "    make stage-mock PACKAGE=hyprland FEDORA_VERSION=44"
	@echo "    make stage-mock PACKAGE=hyprland CMD_TIMEOUT=7200  # 2 hours for large builds"
	@echo "    make full-cycle PACKAGE=hyprland COPR_REPO=nett00n/hyprland"
	@echo ""
	@echo "  Cleanup (when dependency conflicts occur):"
	@echo "    make clean              # Remove build logs"
	@echo "    make clean-localrepo    # Clear local repo RPMs (resolve conflicts)"
	@echo "    make clean-all          # Remove logs and local repo"
	@echo ""
	@echo "  Build artifact tracking (build-report.db):"
	@echo "    make db-usage           # Disk usage by package/target"
	@echo "    make db-prune           # Reclaim space (dry-run; CONFIRM=1 to delete)"
	@echo "    make db-shell           # Interactive sqlite3 shell"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*## ' Makefile | \
		awk -F': ' '{split($$1, parts, " "); split($$2, desc, "## "); printf "  \033[36m%-24s\033[0m %s\n", parts[1], desc[2]}'

setup-venv: ## Create .venv and install Python dependencies
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt

test: check-image check-venv setup-volumes ## Run unit tests for scripts/ using pytest
	$(call run_with_result,$(CONTAINER_PYTHON) -m pytest tests/ -v,Tests passed,Tests failed)

coverage: check-image check-venv setup-volumes ## Run tests with coverage report (--format html for HTML output)
	@mkdir -p "$(MAKE_LOGS_DIR)/coverage"
	@$(CONTAINER_PYTHON) -m pip install -q pytest-cov || exit 1
	@echo "$(HIGHLIGHT_PREFIX) Running coverage analysis..."
	@$(CONTAINER_PYTHON) -m pytest tests/ --cov=scripts --cov-report=term-missing:skip-covered --cov-report=html:.htmlcov -q || exit 1
	@echo "$(HIGHLIGHT_PREFIX) ✓ Coverage report generated"
	@echo "$(HIGHLIGHT_PREFIX) HTML report: .htmlcov/index.html"
	@$(CONTAINER_PYTHON) -m pytest tests/ --cov=scripts --cov-report=json:.htmlcov/coverage.json -q >/dev/null 2>&1 || true

lint: lint-ruff lint-flake lint-mypy lint-rpm lint-yaml ## Run all linters inside container

lint-ruff: check-image check-venv setup-volumes ## Run ruff check on scripts
	$(call run_with_result,$(CONTAINER_PYTHON) -m ruff check scripts/,Ruff check passed,Ruff check failed)

lint-flake: check-image check-venv setup-volumes ## Run flake8 style checker on scripts
	$(CONTAINER_PYTHON) -m pip install -q -r requirements-dev.txt
	$(call run_with_result,$(CONTAINER_PYTHON) -m flake8 scripts/,Flake8 check passed,Flake8 check failed)

lint-mypy: check-image check-venv setup-volumes ## Run mypy type checker on scripts
	$(call run_with_result,$(CONTAINER_PYTHON) -m mypy scripts/ --ignore-missing-imports --exclude submodules,Mypy check passed,Mypy check failed)

lint-rpm: check-image check-venv setup-volumes ## Run rpmlint on all generated spec files
	$(CONTAINER_PYTHON) -m pip install -q rpmlint
	$(call run_with_result,$(CONTAINER_RUN) $(RPMLINT) -r $(WORK)/.rpmlintrc --ignore-unused-rpmlintrc packages/*/[a-z]*.spec,Rpmlint check passed,Rpmlint check failed)

lint-yaml: check-image check-venv setup-volumes ## Run yamllint on YAML files
	$(call run_with_result,$(CONTAINER_PYTHON) -m yamllint *.yaml,Yamllint check passed,Yamllint check failed)

fmt: fmt-ruff fmt-yaml normalize-paths sort-lists ## Format and normalize all files

fmt-ruff: check-image check-venv setup-volumes ## Run ruff format on scripts
	$(call run_with_result,$(CONTAINER_PYTHON) -m ruff format scripts/,Ruff format applied,Ruff format failed)

fmt-yaml: check-image check-venv setup-volumes ## Format YAML files with consistent style
	$(call run_with_result,$(CONTAINER_PYTHON) scripts/format-yaml.py '*.yaml',YAML format applied,YAML format failed)

pre-commit: check-venv ## Run all checks and formatting (test + lint + fmt). Use COVERAGE=1 to include coverage report
	@$(PYTHON) scripts/validate-packages.py || exit 1
	$(MAKE) test lint fmt || exit 1
	@if [ "$(COVERAGE)" = "1" ]; then \
		echo "$(HIGHLIGHT_PREFIX) Running coverage analysis..."; \
		$(MAKE) coverage || exit 1; \
	fi

update-versions: check-image check-venv setup-volumes ## Fetch latest semver tags from submodules and update packages.yaml
	$(CONTAINER_PYTHON) scripts/update-versions.py

list-tags: check-image check-venv setup-volumes ## List all tags for submodules, highlighting latest semver (PACKAGE=<name> for one)
	$(CONTAINER_PYTHON) scripts/list-tags.py $(PACKAGE)

scaffold-package: check-image check-venv setup-volumes ## Scaffold a new packages.yaml entry from a submodule (PACKAGE=<name> required)
	$(CONTAINER_PYTHON) scripts/scaffold-package.py $(PACKAGE)

add-submodule: check-image check-venv setup-volumes ## Register git submodule for an existing package (PACKAGE=<name> required)
	@test -n "$(PACKAGE)" || (echo "$(HIGHLIGHT_PREFIX) Error: PACKAGE is required"; exit 1)
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

delete-package: check-image check-venv setup-volumes ## Remove package from packages.yaml, logs/build, packages/, submodules, and container rpmbuild dirs (PKG=<name> or PACKAGE=<name> required)
	@test -n "$(PACKAGE)" || (echo "$(HIGHLIGHT_PREFIX) Error: PKG or PACKAGE is required (e.g. PKG=hyprpicker)"; exit 1)
	@echo "$(HIGHLIGHT_PREFIX) Removing package '$(PACKAGE)'..."
	@$(CONTAINER_PYTHON) -c "import yaml; d = yaml.safe_load(open('packages.yaml')); d.pop('$(PACKAGE)', None); open('packages.yaml', 'w').write(yaml.dump(d, sort_keys=False))"
	@$(CONTAINER_PYTHON) scripts/db-artifacts.py --forget $(PACKAGE)
	@rm -rf logs/build/$(PACKAGE) packages/$(PACKAGE)
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
	@for ver in $(SUPPORTED); do \
	  vol=rpmbuild-$$ver; \
	  $(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $$vol >/dev/null 2>&1 && \
	    $(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run --rm -v $$vol:/root/rpmbuild:z $(IMAGE_NAME):$$ver \
	      rm -rf /root/rpmbuild/SOURCES/$(PACKAGE)-* /root/rpmbuild/SRPMS/$(PACKAGE)-* /root/rpmbuild/RPMS/*/$(PACKAGE)-* || exit 1; \
	done
	@echo "$(HIGHLIGHT_PREFIX) ✓ Removed $(PACKAGE)"

set-release: check-image check-venv setup-volumes ## Set package release value (PACKAGE=<name|name1,name2,...> RELEASE=<num> required; LOCK=1 to prevent auto-increment)
	@test -n "$(PACKAGE)" || (echo "$(HIGHLIGHT_PREFIX) Error: PACKAGE is required (e.g. PACKAGE=hyprlang or PACKAGE=hyprlang,hyprutils)"; exit 1)
	@test -n "$(RELEASE)" || (echo "$(HIGHLIGHT_PREFIX) Error: RELEASE is required (e.g. RELEASE=5)"; exit 1)
	$(CONTAINER_PYTHON) scripts/set-package-release.py $(PACKAGE) $(RELEASE) $(if $(filter 1,$(LOCK)),--lock,)

gather-requires: check-image check-venv setup-volumes ## Suggest requires entries from built RPMs (PACKAGE=path/to/pkg.rpm required)
	@test -n "$(PACKAGE)" || (echo "$(HIGHLIGHT_PREFIX) Error: PACKAGE is required"; exit 1)
	$(CONTAINER_PYTHON) scripts/gather-requires.py $(PACKAGE)

gen-report: check-image check-venv setup-volumes ## Render build-report.db to stdout for FEDORA_VERSION (--format github|copr)
	$(CONTAINER_RUN) env FEDORA_VERSION=$(FEDORA_VERSION) MOCK_CHROOT=$(MOCK_CHROOT) \
		/work/.venv/bin/python3 scripts/gen-report.py $(if $(FORMAT),--format $(FORMAT),)

readme: check-image check-venv setup-volumes ## Generate README.md, docs/README.copr.md, and docs/full-report.md for FEDORA_VERSION
	@mkdir -p "$(MAKE_LOGS_DIR)/readme"
	@$(CONTAINER_RUN) env FEDORA_VERSION=$(FEDORA_VERSION) MOCK_CHROOT=$(MOCK_CHROOT) \
		/work/.venv/bin/python3 scripts/gen-report.py --format github --output ./README.md \
		2>"$(MAKE_LOGS_DIR)/readme/github.log" || (echo "$(HIGHLIGHT_PREFIX) ✗ GitHub README failed"; exit 1)
	@echo "$(HIGHLIGHT_PREFIX) ✓ GitHub README generated"
	@$(CONTAINER_RUN) env FEDORA_VERSION=$(FEDORA_VERSION) MOCK_CHROOT=$(MOCK_CHROOT) \
		/work/.venv/bin/python3 scripts/gen-report.py --format copr --output ./docs/README.copr.md --skip-copr-poll \
		2>"$(MAKE_LOGS_DIR)/readme/copr.log" || (echo "$(HIGHLIGHT_PREFIX) ✗ COPR README failed"; exit 1)
	@echo "$(HIGHLIGHT_PREFIX) ✓ COPR README generated"
	@$(CONTAINER_RUN) env FEDORA_VERSION=$(FEDORA_VERSION) MOCK_CHROOT=$(MOCK_CHROOT) \
		/work/.venv/bin/python3 scripts/gen-report.py --format full-report --output ./docs/full-report.md --skip-copr-poll \
		2>"$(MAKE_LOGS_DIR)/readme/full-report.log" || (echo "$(HIGHLIGHT_PREFIX) ✗ Full Report failed"; exit 1)
	@echo "$(HIGHLIGHT_PREFIX) ✓ Full Report generated"

readme-shell: check-image check-venv ## Regenerate only the branding shell of README.md/docs/README.copr.md (no build-report.db needed; for CI)
	$(call run_with_result,$(CONTAINER_PYTHON) scripts/gen-readme-shell.py,Readme shell updated,Readme shell update failed)

db-usage: check-image check-venv setup-volumes ## Report disk usage of tracked build artifacts by package/target
	@$(CONTAINER_PYTHON) scripts/db-artifacts.py --usage

db-prune: check-image check-venv setup-volumes ## Remove all but the newest artifact per (package,target,kind). Dry-run by default; CONFIRM=1 to actually delete
	@$(CONTAINER_PYTHON) scripts/db-artifacts.py --prune $(if $(filter 1,$(CONFIRM)),--confirm,)

db-shell: check-image check-venv ## Open an interactive sqlite3 shell on build-report.db
	@$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run -it --rm \
		-v $(WORKDIR_MOUNT) \
		-v $(VENV_MOUNT) \
		-w /work \
		$(IMAGE_NAME):$(FEDORA_VERSION) /work/.venv/bin/python3 -m sqlite3 build-report.db

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

container-build: ## Build image for FEDORA_VERSION
	$(call run_with_result,$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) build \
		--build-arg FEDORA_VERSION=$(FEDORA_VERSION) \
		--build-arg UID=$(USER_ID) \
		--build-arg GID=$(GROUP_ID) \
		-t $(IMAGE_NAME):$(FEDORA_VERSION) \
		-f Containerfile .,Built $(IMAGE_NAME):$(FEDORA_VERSION),Container build failed)

container-enter: ## Enter interactive shell in container for FEDORA_VERSION
	$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run -it --rm \
		-v $(RPMBUILD_MOUNT) \
		-v $(LOCALREPO_MOUNT) \
		-v $(WORKDIR_MOUNT) \
		-w /work \
		$(IMAGE_NAME):$(FEDORA_VERSION) /bin/bash

container-clean: ## Remove image for FEDORA_VERSION
	$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) image inspect $(IMAGE_NAME):$(FEDORA_VERSION) >/dev/null 2>&1 && \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) rmi $(IMAGE_NAME):$(FEDORA_VERSION) || true
	@echo $(HIGHLIGHT_PREFIX) "Cleaned $(IMAGE_NAME):$(FEDORA_VERSION)"

container-volume-clean: ## Remove volumes (rpmbuild, local-repo) for FEDORA_VERSION (all if not specified)
	@if [ "$(FEDORA_VERSION)" = "43" ] && [ -z "$(RECURSIVE_CALL)" ]; then \
		for v in $(SUPPORTED); do \
			echo $(HIGHLIGHT_PREFIX) "Removing volumes for Fedora $$v..."; \
			$(MAKE) container-volume-clean FEDORA_VERSION=$$v RECURSIVE_CALL=1 || exit 1; \
		done; \
		echo $(HIGHLIGHT_PREFIX) "All volumes cleaned"; \
	else \
		echo $(HIGHLIGHT_PREFIX) "Removing volumes for Fedora $(FEDORA_VERSION)..."; \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(RPMBUILD_VOLUME) >/dev/null 2>&1 && \
			$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume rm $(RPMBUILD_VOLUME) || true; \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(LOCALREPO_VOLUME) >/dev/null 2>&1 && \
			$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume rm $(LOCALREPO_VOLUME) || true; \
		echo $(HIGHLIGHT_PREFIX) "Cleaned volumes: $(RPMBUILD_VOLUME), $(LOCALREPO_VOLUME)"; \
	fi

container-all: ## Build images for all supported Fedora versions
	@for v in $(SUPPORTED); do \
		echo $(HIGHLIGHT_PREFIX) "Fedora $$v"; \
		$(MAKE) container-build FEDORA_VERSION=$$v; \
	done

sources: check-image setup-volumes ## Download sources for PACKAGE (or all) using spectool (runs in container)
	@for pkg in $(_PKGS); do \
		_spec="packages/$$pkg/$$pkg.spec"; \
		if [ ! -f "$$_spec" ]; then \
			echo "$(HIGHLIGHT_PREFIX) ✗ sources: $$pkg - spec file not found: $$_spec"; exit 1; \
		fi; \
		echo "$(HIGHLIGHT_PREFIX) sources: $$pkg"; \
		$(CONTAINER_RUN) spectool -g -R $$_spec || exit 1; \
	done

FORCE_MOCK ?=
PROCEED_BUILD ?=
SKIP_MOCK ?=
SKIP_COPR ?=
DRY_RUN ?=
SYNCHRONOUS_COPR_BUILD ?=
REQUIRE_CHROOT_COVERAGE ?=

full-cycle: check-image check-venv setup-volumes ## Run full cycle with YAML report: spec → srpm → mock → copr (PACKAGE, COPR_REPO, env vars)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		COPR_REPO=$(COPR_REPO) \
		FORCE_MOCK=$(FORCE_MOCK) \
		PROCEED_BUILD=$(PROCEED_BUILD) \
		SKIP_MOCK=$(SKIP_MOCK) \
		SKIP_COPR=$(SKIP_COPR) \
		DRY_RUN=$(DRY_RUN) \
		SYNCHRONOUS_COPR_BUILD=$(SYNCHRONOUS_COPR_BUILD) \
		REQUIRE_CHROOT_COVERAGE=$(REQUIRE_CHROOT_COVERAGE) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/full-cycle.py,Full cycle completed,Full cycle failed)

MATRIX_VERSIONS ?= $(SUPPORTED)

full-cycle-matrix: ## Build every MATRIX_VERSIONS chroot locally (default: all SUPPORTED, x86_64 only), then submit to Copr once (PACKAGE, COPR_REPO, requires 'make container-all' first)
	@for v in $(MATRIX_VERSIONS); do \
		echo $(HIGHLIGHT_PREFIX) "Fedora $$v"; \
		$(MAKE) full-cycle FEDORA_VERSION=$$v PACKAGE=$(PACKAGE) SKIP_COPR=true || exit 1; \
	done
	@if [ -n "$(COPR_REPO)" ]; then \
		$(MAKE) stage-copr FEDORA_VERSION=$(FEDORA_VERSION) PACKAGE=$(PACKAGE) COPR_REPO=$(COPR_REPO) \
			REQUIRE_CHROOT_COVERAGE=$(REQUIRE_CHROOT_COVERAGE); \
	else \
		echo $(HIGHLIGHT_PREFIX) "COPR_REPO not set -- skipping Copr submission (local matrix build only)"; \
	fi

update-daily: ## Update versions, gate (validate+test+lint+fmt), build, generate docs, push to COPR (requires COPR_REPO), git commit (PUSH=1 to also git push)
	@test -n "$(COPR_REPO)" || (echo "$(HIGHLIGHT_PREFIX) Error: COPR_REPO is not set (e.g. export COPR_REPO=nett00n/hyprland)"; exit 1)
	$(MAKE) update-versions pre-commit full-cycle readme copr-description || exit 1
	git add packages.yaml packages/ submodules/ README.md docs/README.copr.md docs/full-report.md || exit 1
	@if git diff --cached --quiet; then \
		echo "$(HIGHLIGHT_PREFIX) Nothing to commit (no version/doc changes tonight)."; \
	else \
		git commit -m "Daily update: $$(date --rfc-3339=seconds)" || exit 1; \
		if [ "$(PUSH)" = "1" ]; then \
			git pull --rebase origin main || exit 1; \
			git push || exit 1; \
		fi; \
	fi

build-pop: check-image check-venv setup-volumes ## Remove mock/copr build status for PKG=a,b (PKG="" removes all, requires confirmation)
	@if [ -z "$(PACKAGE)" ]; then \
		printf "$(HIGHLIGHT_PREFIX) Remove mock/copr status for ALL packages? [y/N] "; \
		read ans; \
		[ "$$ans" = "y" ] || [ "$$ans" = "Y" ] || { echo "$(HIGHLIGHT_PREFIX) Aborted."; exit 1; }; \
	fi
	@$(CONTAINER_RUN) env FEDORA_VERSION=$(FEDORA_VERSION) MOCK_CHROOT=$(MOCK_CHROOT) PACKAGE=$(PACKAGE) \
		/work/.venv/bin/python3 scripts/pkg-build-pop.py || exit 1

stage-validate: check-image check-venv setup-volumes ## Run validation stage (PACKAGE=<name>, CMD_TIMEOUT, runs in container)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/stage-validate.py,Validation stage passed,Validation stage failed)

stage-show-plan: check-image check-venv setup-volumes ## Show build plan - what will run, cache, or skip (PACKAGE, SKIP_PACKAGES, COPR_REPO optional, runs in container)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		SKIP_PACKAGES=$(SKIP_PACKAGES) \
		COPR_REPO=$(COPR_REPO) \
		/work/.venv/bin/python3 scripts/stage-show-plan.py,Build plan displayed,Build plan failed)

stage-spec: check-image check-venv setup-volumes ## Run spec generation stage (PACKAGE=<name>, CMD_TIMEOUT, runs in container)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/stage-spec.py,Spec generation passed,Spec generation failed)

stage-vendor: check-image check-venv setup-volumes ## Run vendor tarball generation stage (Go/Rust packages, PACKAGE=<name>, CMD_TIMEOUT, runs in container)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/stage-vendor.py,Vendor stage passed,Vendor stage failed)

stage-srpm: check-image check-venv setup-volumes ## Run SRPM build stage (PACKAGE=<name>, CMD_TIMEOUT, runs in container)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/stage-srpm.py,SRPM stage passed,SRPM stage failed)

stage-mock: check-image check-venv setup-volumes ## Run mock build stage (PACKAGE=<name>, FEDORA_VERSION, CMD_TIMEOUT, runs in container)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/stage-mock.py,Mock build stage passed,Mock build stage failed)

stage-copr: check-image check-venv setup-volumes ## Run Copr submission stage (PACKAGE=<name>, COPR_REPO required, REQUIRE_CHROOT_COVERAGE, CMD_TIMEOUT, runs in container)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		COPR_REPO=$(COPR_REPO) \
		REQUIRE_CHROOT_COVERAGE=$(REQUIRE_CHROOT_COVERAGE) \
		$(if $(CMD_TIMEOUT),CMD_TIMEOUT=$(CMD_TIMEOUT),) \
		/work/.venv/bin/python3 scripts/stage-copr.py,Copr submission stage passed,Copr submission stage failed)

stage-log-analyze: check-image check-venv setup-volumes ## Analyze build logs for packages and report actionable errors (PACKAGE=<name> for one, runs for all by default, respects SKIP_PACKAGES)
	@for pkg in $(_PKGS); do \
		_skip_list="$(SKIP_PACKAGES)"; \
		if [ -n "$$_skip_list" ]; then \
			_match=0; \
			for _skip in $$(echo "$$_skip_list" | tr ',' ' '); do \
				[ "$$pkg" = "$$_skip" ] && _match=1 && break; \
			done; \
			[ $$_match -eq 1 ] && { echo "$(HIGHLIGHT_PREFIX) ⊘ Skipping: $$pkg"; continue; }; \
		fi; \
		echo "$(HIGHLIGHT_PREFIX) Analyzing: $$pkg"; \
		$(CONTAINER_PYTHON) scripts/pkg-log-analysis.py $$pkg || exit 1; \
	done
