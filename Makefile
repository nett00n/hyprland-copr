# Load .env file if it exists (allows declaring defaults without overriding env exports)
-include .env
# Strip quotes from .env variables (shell syntax vs make syntax)
FEDORA_VERSION  := $(subst ",,$(FEDORA_VERSION))
COPR_REPO       := $(subst ",,$(COPR_REPO))
PACKAGE         := $(subst ",,$(PACKAGE))
SKIP_PACKAGES   := $(subst ",,$(SKIP_PACKAGES))
QUIET           := $(subst ",,$(QUIET))
# Fallback defaults if not set after stripping
FEDORA_VERSION  ?= 43
SUPPORTED        := 42 43 44 rawhide
IMAGE_NAME       := rpm-toolbox
HIGHLIGHT_PREFIX ?= "█▓▒░"

# Accept either PACKAGE or PKG; PACKAGE takes precedence
PACKAGE      ?=
PKG          ?=
PACKAGE      := $(or $(PACKAGE),$(PKG))

# Skip packages during dependency gathering (comma-separated list)
SKIP_PACKAGES ?=

# Quiet mode: QUIET=1 suppresses output and saves to logs
QUIET        ?=
MAKE_LOGS_DIR := ./logs/make

ifeq ($(FEDORA_VERSION),rawhide)
  MOCK_CHROOT := fedora-rawhide-x86_64
else
  MOCK_CHROOT := fedora-$(FEDORA_VERSION)-x86_64
endif

# Container runtime: podman (default) or docker (fallback)
CONTAINER_RUNTIME ?= $(shell command -v podman >/dev/null 2>&1 && echo podman || echo docker)
CONTAINER_SUDO    := $(if $(filter docker,$(CONTAINER_RUNTIME)),sudo,)

# User ID/GID detection for rootless containers
USER_ID      := $(shell id -u)
GROUP_ID     := $(shell id -g)
HOME_DIR     := $(shell echo $$HOME)

# Per-Fedora-version volumes (container user is set in Containerfile)
RPMBUILD_VOLUME  := rpmbuild-$(FEDORA_VERSION)
RPMBUILD_MOUNT   := $(RPMBUILD_VOLUME):/home/user/rpmbuild:z
LOCALREPO_VOLUME := local-repo-$(FEDORA_VERSION)
LOCALREPO_MOUNT  := $(LOCALREPO_VOLUME):/local-repo:z
WORKDIR_MOUNT    := $(PWD):/work:z
VENV_MOUNT       := $(PWD)/.venv:/work/.venv:z
MOCK_CONF_MOUNT  := $(PWD)/mock-local-repo.conf:/etc/mock/local-repo.conf:ro,z
COPR_MOUNT_OPT   := ro,z
COPR_CONFIG_MOUNT := $(if $(COPR_REPO),-v $(HOME_DIR)/.config/copr:/root/.config/copr:$(COPR_MOUNT_OPT),)

# Setup volumes with correct permissions (UID/GID from host user)
define setup_volumes
	@if ! $(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(RPMBUILD_VOLUME) &>/dev/null; then \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume create $(RPMBUILD_VOLUME); \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run --rm -v $(RPMBUILD_MOUNT) $(IMAGE_NAME):$(FEDORA_VERSION) \
			chown -R $(USER_ID):$(GROUP_ID) /home/user/rpmbuild; \
	fi
	@if ! $(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume inspect $(LOCALREPO_VOLUME) &>/dev/null; then \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume create $(LOCALREPO_VOLUME); \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run --rm -v $(LOCALREPO_MOUNT) $(IMAGE_NAME):$(FEDORA_VERSION) \
			chown -R $(USER_ID):$(GROUP_ID) /local-repo; \
	fi
endef

# Container execution with volume mounts
# Note: Containerfile already sets USER, so don't override it here
# --privileged flag is required for mock to work (namespace support)
CONTAINER_RUN := $(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run --rm --privileged \
	-v $(RPMBUILD_MOUNT) \
	-v $(LOCALREPO_MOUNT) \
	-v $(WORKDIR_MOUNT) \
	-v $(VENV_MOUNT) \
	-v $(MOCK_CONF_MOUNT) \
	$(COPR_CONFIG_MOUNT) \
	-w /work \
	$(IMAGE_NAME):$(FEDORA_VERSION)

# Python in container using mounted .venv
CONTAINER_PYTHON := $(CONTAINER_RUN) /work/.venv/bin/python3

ALL_PACKAGES := $(shell grep -oP '^[a-zA-Z][a-zA-Z0-9_-]+(?=:)' packages.yaml)
_PKGS        := $(if $(PACKAGE),$(PACKAGE),$(ALL_PACKAGES))

PYTHON           := .venv/bin/python3
README_COPR      := docs/README.copr.md
COPR_INSTRUCTIONS := docs/INSTALL.copr.md

# Helper: run command with optional logging
# Usage: $(call run_with_result,command,success_msg,fail_msg,log_dir)
define run_with_result
	@if [ "$(QUIET)" = "1" ] && [ -n "$4" ]; then \
		mkdir -p "$4"; \
		rm -f "$4"/*.log; \
		if $1 > "$4/stdout.log" 2> "$4/stderr.log"; then \
			echo $(HIGHLIGHT_PREFIX) "✓ $2"; \
			_out=$$(wc -l < "$4/stdout.log" 2>/dev/null || echo 0); \
			_err=$$(wc -l < "$4/stderr.log" 2>/dev/null || echo 0); \
			echo $(HIGHLIGHT_PREFIX) "  stdout ($${_out} lines): $4/stdout.log"; \
			echo $(HIGHLIGHT_PREFIX) "  stderr ($${_err} lines): $4/stderr.log"; \
		else \
			echo $(HIGHLIGHT_PREFIX) "✗ $3"; \
			_out=$$(wc -l < "$4/stdout.log" 2>/dev/null || echo 0); \
			_err=$$(wc -l < "$4/stderr.log" 2>/dev/null || echo 0); \
			echo $(HIGHLIGHT_PREFIX) "  stdout ($${_out} lines): $4/stdout.log"; \
			echo $(HIGHLIGHT_PREFIX) "  stderr ($${_err} lines): $4/stderr.log"; \
			exit 1; \
		fi; \
	else \
		$1 && echo $(HIGHLIGHT_PREFIX) "✓ $2" || (echo $(HIGHLIGHT_PREFIX) "✗ $3"; exit 1); \
	fi
endef


.DEFAULT_GOAL := help
.PHONY: help setup-venv lint fmt pre-commit ruff ruff-format flake mypy rpmlint yamlfmt yamllint pkg-spec update-versions list-tags scaffold-package add-submodule add-package add-new gen-report readme copr-description normalize-paths sort-lists container-build container-enter container-clean container-volume-clean container-all pkg-sources pkg-srpm pkg-mock pkg-copr pkg-full-cycle pkg-build-pop pkg-log-analysis stage-validate stage-spec stage-vendor stage-srpm stage-mock stage-copr

help: ## Show this help
	@echo "Usage: make [TARGET] [PACKAGE=<name>] [FEDORA_VERSION=<version>]"
	@echo ""
	@echo "  Supported versions : $(SUPPORTED)"
	@echo "  Default version    : 43"
	@echo ""
	@echo "  Examples:"
	@echo "    make pkg-srpm PACKAGE=hyprland"
	@echo "    make pkg-mock PACKAGE=hyprland FEDORA_VERSION=42"
	@echo "    make pkg-log-analysis PKG=hyprland-plugins"
	@echo "    make pkg-copr PACKAGE=hyprland"
	@echo "    make stage-spec stage-srpm stage-mock PACKAGE=hyprutils"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

setup-venv: ## Create .venv and install Python dependencies
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt

lint: ## Run all linters inside container (ruff, flake8, mypy, rpmlint, yamllint)
	$(setup_volumes)
	$(CONTAINER_PYTHON) -m pip install -q -r requirements-dev.txt
	@if [ -z "$(QUIET)" ]; then echo $(HIGHLIGHT_PREFIX) "Ruff (Python linter)"; fi
	$(call run_with_result,$(CONTAINER_PYTHON) -m ruff check scripts/,Ruff check passed,Ruff check failed,$(MAKE_LOGS_DIR)/lint/ruff)
	@if [ -z "$(QUIET)" ]; then echo $(HIGHLIGHT_PREFIX) "Flake8 (Style checker)"; fi
	$(call run_with_result,$(CONTAINER_PYTHON) -m flake8 scripts/,Flake8 check passed,Flake8 check failed,$(MAKE_LOGS_DIR)/lint/flake)
	@if [ -z "$(QUIET)" ]; then echo $(HIGHLIGHT_PREFIX) "Mypy (Type checker)"; fi
	$(call run_with_result,$(CONTAINER_PYTHON) -m mypy scripts/ --ignore-missing-imports --exclude submodules,Mypy check passed,Mypy check failed,$(MAKE_LOGS_DIR)/lint/mypy)
	@if [ -z "$(QUIET)" ]; then echo $(HIGHLIGHT_PREFIX) "Rpmlint (RPM spec linter)"; fi
	$(call run_with_result,$(CONTAINER_RUN) rpmlint packages/*/[a-z]*.spec,Rpmlint check passed,Rpmlint check failed,$(MAKE_LOGS_DIR)/lint/rpmlint)
	@if [ -z "$(QUIET)" ]; then echo $(HIGHLIGHT_PREFIX) "Yamllint (YAML validator)"; fi
	$(call run_with_result,$(CONTAINER_PYTHON) -m yamllint *.yaml,Yamllint check passed,Yamllint check failed,$(MAKE_LOGS_DIR)/lint/yamllint)

fmt: ## Format and normalize: ruff format, YAML format, paths, and YAML lists
	$(setup_volumes)
	$(CONTAINER_PYTHON) -m pip install -q -r requirements-dev.txt
	$(call run_with_result,$(CONTAINER_PYTHON) -m ruff format scripts/,Ruff format applied,Ruff format failed,$(MAKE_LOGS_DIR)/fmt/ruff)
	$(call run_with_result,$(PYTHON) scripts/format-yaml.py '*.yaml',YAML format applied,YAML format failed,$(MAKE_LOGS_DIR)/fmt/yamlfmt)
	$(call run_with_result,$(PYTHON) scripts/rpm-dir-prefixes-convert.py,RPM dir prefixes normalized,RPM dir prefixes failed,$(MAKE_LOGS_DIR)/fmt/rpm-dir)
	$(call run_with_result,$(PYTHON) scripts/sort-yaml-lists.py,YAML lists sorted,YAML lists sorting failed,$(MAKE_LOGS_DIR)/fmt/sort-yaml)

pre-commit: ## Run all checks and formatting (lint + fmt)
	$(setup_volumes)
	$(call run_with_result,$(CONTAINER_PYTHON) -m pip install -q -r requirements-dev.txt,Dev deps installed,Dev deps failed,$(MAKE_LOGS_DIR)/pre-commit/pip)
	$(call run_with_result,$(CONTAINER_PYTHON) -m ruff check scripts/,Ruff check passed,Ruff check failed,$(MAKE_LOGS_DIR)/pre-commit/ruff)
	$(call run_with_result,$(CONTAINER_PYTHON) -m ruff format scripts/,Ruff format applied,Ruff format failed,$(MAKE_LOGS_DIR)/pre-commit/ruff-format)
	$(call run_with_result,$(CONTAINER_PYTHON) -m flake8 scripts/,Flake8 check passed,Flake8 check failed,$(MAKE_LOGS_DIR)/pre-commit/flake)
	$(call run_with_result,$(CONTAINER_PYTHON) -m mypy scripts/ --ignore-missing-imports --exclude submodules,Mypy check passed,Mypy check failed,$(MAKE_LOGS_DIR)/pre-commit/mypy)
	$(call run_with_result,$(CONTAINER_RUN) rpmlint packages/*/[a-z]*.spec,Rpmlint check passed,Rpmlint check failed,$(MAKE_LOGS_DIR)/pre-commit/rpmlint)
	$(call run_with_result,$(PYTHON) scripts/format-yaml.py '*.yaml',YAML format applied,YAML format failed,$(MAKE_LOGS_DIR)/pre-commit/yamlfmt)
	$(call run_with_result,$(CONTAINER_PYTHON) -m yamllint *.yaml,Yamllint check passed,Yamllint check failed,$(MAKE_LOGS_DIR)/pre-commit/yamllint)
	$(call run_with_result,$(PYTHON) scripts/rpm-dir-prefixes-convert.py,RPM dir prefixes normalized,RPM dir prefixes failed,$(MAKE_LOGS_DIR)/pre-commit/rpm-dir)
	$(call run_with_result,$(PYTHON) scripts/sort-yaml-lists.py,YAML lists sorted,YAML lists sorting failed,$(MAKE_LOGS_DIR)/pre-commit/sort-yaml)

ruff: ## Run ruff check on scripts
	$(setup_volumes)
	$(call run_with_result,$(CONTAINER_PYTHON) -m ruff check scripts/,Ruff check passed,Ruff check failed,$(MAKE_LOGS_DIR)/ruff)

ruff-format: ## Run ruff format on scripts
	$(setup_volumes)
	$(call run_with_result,$(CONTAINER_PYTHON) -m ruff format scripts/,Ruff format passed,Ruff format failed,$(MAKE_LOGS_DIR)/ruff-format)

flake: ## Run flake8 style checker on scripts
	$(setup_volumes)
	$(CONTAINER_PYTHON) -m pip install -q -r requirements-dev.txt
	$(call run_with_result,$(CONTAINER_PYTHON) -m flake8 scripts/,Flake8 check passed,Flake8 check failed,$(MAKE_LOGS_DIR)/flake)

mypy: ## Run mypy type checker on scripts
	$(setup_volumes)
	$(call run_with_result,$(CONTAINER_PYTHON) -m mypy scripts/ --ignore-missing-imports --exclude submodules,Mypy check passed,Mypy check failed,$(MAKE_LOGS_DIR)/mypy)

yamlfmt: ## Format YAML files with consistent style
	$(call run_with_result,$(PYTHON) scripts/format-yaml.py '*.yaml',YAML format applied,YAML format failed,$(MAKE_LOGS_DIR)/yamlfmt)

yamllint: ## Run yamllint on YAML files
	$(setup_volumes)
	$(call run_with_result,$(CONTAINER_PYTHON) -m yamllint *.yaml,Yamllint check passed,Yamllint check failed,$(MAKE_LOGS_DIR)/yamllint)

rpmlint: ## Run rpmlint on all generated spec files
	$(setup_volumes)
	$(CONTAINER_PYTHON) -m pip install -q rpmlint
	$(call run_with_result,$(CONTAINER_RUN) rpmlint packages/*/[a-z]*.spec,Rpmlint check passed,Rpmlint check failed,$(MAKE_LOGS_DIR)/rpmlint)

pkg-spec: ## Generate spec file(s) from packages.yaml (PACKAGE=<name> for one package)
	$(PYTHON) scripts/gen-spec.py $(PACKAGE)

update-versions: ## Fetch latest semver tags from submodules and update packages.yaml
	$(PYTHON) scripts/update-versions.py

list-tags: ## List all tags for submodules, highlighting latest semver (PACKAGE=<name> for one)
	$(PYTHON) scripts/list-tags.py $(PACKAGE)

scaffold-package: ## Scaffold a new packages.yaml entry from a submodule (PACKAGE=<name> required)
	$(PYTHON) scripts/scaffold-package.py $(PACKAGE)

add-submodule: ## Register git submodule for an existing package (PACKAGE=<name> required)
	@test -n "$(PACKAGE)" || (echo "Error: PACKAGE is required"; exit 1)
	@_url=$$($(PYTHON) -c "import yaml; d=yaml.safe_load(open('packages.yaml')); print(d['$(PACKAGE)']['url'])"); \
	 _name=$$(basename $$_url); \
	 _org=$$(basename $$(dirname $$_url)); \
	 echo $(HIGHLIGHT_PREFIX) "adding submodule submodules/$$_org/$$_name"; \
	 git submodule add $$_url submodules/$$_org/$$_name

add-package: ## Scaffold a packages.yaml entry from an existing submodule (PACKAGE=<name> required)
	$(PYTHON) scripts/scaffold-package.py $(PACKAGE)

add-new: ## Add submodule from URL and scaffold packages.yaml entry in one step (URL=<repo-url> required)
	@test -n "$(URL)" || (echo "Error: URL is required (e.g. URL=https://github.com/hyprwm/hyprpicker)"; exit 1)
	@_name=$$(basename $(URL:.git=)); \
	 _org=$$(basename $$(dirname $(URL))); \
	 git submodule add $(URL) submodules/$$_org/$$_name && \
	 $(PYTHON) scripts/scaffold-package.py $$_name

gen-report: ## Render build-report.yaml to stdout (--format github|copr)
	$(PYTHON) scripts/gen-report.py $(if $(FORMAT),--format $(FORMAT),)

readme: ## Generate README.md, docs/README.copr.md, and docs/README.full-report.md
	@if [ -n "$(QUIET)" ]; then \
		mkdir -p "$(MAKE_LOGS_DIR)/readme"; \
		$(PYTHON) scripts/gen-report.py --format github > ./README.md \
			2>"$(MAKE_LOGS_DIR)/readme/github.log" \
			&& echo $(HIGHLIGHT_PREFIX) "✓ GitHub README generated" \
			|| (echo $(HIGHLIGHT_PREFIX) "✗ GitHub README failed"; exit 1); \
		$(PYTHON) scripts/gen-report.py --format copr > ./docs/README.copr.md \
			2>"$(MAKE_LOGS_DIR)/readme/copr.log" \
			&& echo $(HIGHLIGHT_PREFIX) "✓ COPR README generated" \
			|| (echo $(HIGHLIGHT_PREFIX) "✗ COPR README failed"; exit 1); \
		$(PYTHON) scripts/gen-report.py --format full-report > ./docs/README.full-report.md \
			2>"$(MAKE_LOGS_DIR)/readme/full-report.log" \
			&& echo $(HIGHLIGHT_PREFIX) "✓ Full Report generated" \
			|| (echo $(HIGHLIGHT_PREFIX) "✗ Full Report failed"; exit 1); \
	else \
		$(PYTHON) scripts/gen-report.py --format github > ./README.md && echo $(HIGHLIGHT_PREFIX) "✓ GitHub README generated" || (echo $(HIGHLIGHT_PREFIX) "✗ GitHub README failed"; exit 1); \
		$(PYTHON) scripts/gen-report.py --format copr > ./docs/README.copr.md && echo $(HIGHLIGHT_PREFIX) "✓ COPR README generated" || (echo $(HIGHLIGHT_PREFIX) "✗ COPR README failed"; exit 1); \
		$(PYTHON) scripts/gen-report.py --format full-report > ./docs/README.full-report.md && echo $(HIGHLIGHT_PREFIX) "✓ Full Report generated" || (echo $(HIGHLIGHT_PREFIX) "✗ Full Report failed"; exit 1); \
	fi

# Update the COPR project description and instructions from markdown files.
# Requires: copr-cli installed + ~/.config/copr token
copr-description: $(README_COPR) $(COPR_INSTRUCTIONS) ## Push description and install instructions to COPR (COPR_REPO required)
	@test -n "$(COPR_REPO)" || (echo "Error: COPR_REPO is not set (e.g. export COPR_REPO=nett00n/hyprland)"; exit 1)
	$(CONTAINER_RUN) copr-cli modify "$(COPR_REPO)" \
		--description "$$(cat $(README_COPR))" \
		--instructions "$$(cat $(COPR_INSTRUCTIONS))"
	@echo $(HIGHLIGHT_PREFIX) "Description updated → $(COPR_REPO)"

normalize-paths: ## Normalize paths in packages.yaml abs->macros (ARGS=--reverse or --dry-run)
	$(PYTHON) scripts/rpm-dir-prefixes-convert.py $(ARGS)

sort-lists: ## Sort build_requires/requires/files lists in packages.yaml (ARGS=--dry-run)
	$(PYTHON) scripts/sort-yaml-lists.py $(ARGS)

container-build: ## Build image for FEDORA_VERSION
	$(call run_with_result,$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) build \
		--build-arg FEDORA_VERSION=$(FEDORA_VERSION) \
		--build-arg UID=$(USER_ID) \
		--build-arg GID=$(GROUP_ID) \
		-t $(IMAGE_NAME):$(FEDORA_VERSION) \
		-f Containerfile .,Built $(IMAGE_NAME):$(FEDORA_VERSION),Container build failed,$(MAKE_LOGS_DIR)/container-build)

container-enter: ## Enter interactive shell in container for FEDORA_VERSION
	$(setup_volumes)
	$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) run -it --rm \
		-v $(RPMBUILD_MOUNT) \
		-v $(LOCALREPO_MOUNT) \
		-v $(WORKDIR_MOUNT) \
		-w /work \
		$(IMAGE_NAME):$(FEDORA_VERSION) /bin/bash

container-clean: ## Remove image for FEDORA_VERSION
	-$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) rmi $(IMAGE_NAME):$(FEDORA_VERSION)
	@echo $(HIGHLIGHT_PREFIX) "Cleaned $(IMAGE_NAME):$(FEDORA_VERSION)"

container-volume-clean: ## Remove volumes (rpmbuild, local-repo) for FEDORA_VERSION (all if not specified)
	@if [ "$(FEDORA_VERSION)" = "43" ] && [ -z "$(RECURSIVE_CALL)" ]; then \
		for v in $(SUPPORTED); do \
			echo $(HIGHLIGHT_PREFIX) "Removing volumes for Fedora $$v..."; \
			$(MAKE) container-volume-clean FEDORA_VERSION=$$v RECURSIVE_CALL=1; \
		done; \
		echo $(HIGHLIGHT_PREFIX) "All volumes cleaned"; \
	else \
		echo $(HIGHLIGHT_PREFIX) "Removing volumes for Fedora $(FEDORA_VERSION)..."; \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume rm $(RPMBUILD_VOLUME) || true; \
		$(CONTAINER_SUDO) $(CONTAINER_RUNTIME) volume rm $(LOCALREPO_VOLUME) || true; \
		echo $(HIGHLIGHT_PREFIX) "Cleaned volumes: $(RPMBUILD_VOLUME), $(LOCALREPO_VOLUME)"; \
	fi

container-all: ## Build images for all supported Fedora versions
	@for v in $(SUPPORTED); do \
		echo $(HIGHLIGHT_PREFIX) "Fedora $$v"; \
		$(MAKE) container-build FEDORA_VERSION=$$v; \
	done

pkg-sources: ## Download sources for PACKAGE (or all) using spectool (runs in container)
	$(setup_volumes)
	@for pkg in $(_PKGS); do \
		if [ -n "$(QUIET)" ]; then \
			_ld="$(MAKE_LOGS_DIR)/pkg-sources/$$pkg"; mkdir -p "$$_ld"; \
			if $(CONTAINER_RUN) spectool -g -R packages/$$pkg/$$pkg.spec > "$$_ld/stdout.log" 2> "$$_ld/stderr.log"; then \
				echo $(HIGHLIGHT_PREFIX) "✓ sources: $$pkg"; \
			else \
				echo $(HIGHLIGHT_PREFIX) "✗ sources: $$pkg"; exit 1; \
			fi; \
		else \
			echo $(HIGHLIGHT_PREFIX) "sources: $$pkg"; \
			$(CONTAINER_RUN) spectool -g -R packages/$$pkg/$$pkg.spec || exit 1; \
		fi; \
	done

pkg-srpm: ## Build SRPM for PACKAGE (or all) (runs in container)
	$(setup_volumes)
	@for pkg in $(_PKGS); do \
		if [ -n "$(QUIET)" ]; then \
			_ld="$(MAKE_LOGS_DIR)/pkg-srpm/$$pkg"; mkdir -p "$$_ld"; \
			if $(CONTAINER_RUN) spectool -g -R packages/$$pkg/$$pkg.spec >> "$$_ld/stdout.log" 2>> "$$_ld/stderr.log" && \
			   $(CONTAINER_RUN) rpmbuild -bs packages/$$pkg/$$pkg.spec >> "$$_ld/stdout.log" 2>> "$$_ld/stderr.log"; then \
				echo $(HIGHLIGHT_PREFIX) "✓ srpm: $$pkg"; \
			else \
				echo $(HIGHLIGHT_PREFIX) "✗ srpm: $$pkg"; exit 1; \
			fi; \
		else \
			echo $(HIGHLIGHT_PREFIX) "srpm: $$pkg"; \
			$(CONTAINER_RUN) spectool -g -R packages/$$pkg/$$pkg.spec || exit 1; \
			$(CONTAINER_RUN) rpmbuild -bs packages/$$pkg/$$pkg.spec || exit 1; \
		fi; \
	done

pkg-mock: ## Build and test PACKAGE (or all) with mock for FEDORA_VERSION (runs in container)
	$(setup_volumes)
	@for pkg in $(_PKGS); do \
		if [ -n "$(QUIET)" ]; then \
			_ld="$(MAKE_LOGS_DIR)/pkg-mock/$$pkg"; mkdir -p "$$_ld"; \
			if $(CONTAINER_RUN) spectool -g -R packages/$$pkg/$$pkg.spec >> "$$_ld/stdout.log" 2>> "$$_ld/stderr.log" && \
			   $(CONTAINER_RUN) rpmbuild -bs packages/$$pkg/$$pkg.spec >> "$$_ld/stdout.log" 2>> "$$_ld/stderr.log"; then \
				srpm=$$(ls -t ~/rpmbuild/SRPMS/$$pkg-*.src.rpm 2>/dev/null | head -1); \
				if [ -n "$$srpm" ] && $(CONTAINER_RUN) mock -r $(MOCK_CHROOT) --rebuild $$srpm >> "$$_ld/stdout.log" 2>> "$$_ld/stderr.log"; then \
					echo $(HIGHLIGHT_PREFIX) "✓ mock-build: $$pkg"; \
				else \
					echo $(HIGHLIGHT_PREFIX) "✗ mock-build: $$pkg"; exit 1; \
				fi; \
			else \
				echo $(HIGHLIGHT_PREFIX) "✗ srpm: $$pkg"; exit 1; \
			fi; \
		else \
			echo $(HIGHLIGHT_PREFIX) "sources: $$pkg"; \
			$(CONTAINER_RUN) spectool -g -R packages/$$pkg/$$pkg.spec || exit 1; \
			echo $(HIGHLIGHT_PREFIX) "srpm: $$pkg"; \
			$(CONTAINER_RUN) rpmbuild -bs packages/$$pkg/$$pkg.spec || exit 1; \
			echo $(HIGHLIGHT_PREFIX) "mock-build: $$pkg"; \
			srpm=$$(ls -t ~/rpmbuild/SRPMS/$$pkg-*.src.rpm 2>/dev/null | head -1); \
			test -n "$$srpm" || { echo "ERROR: no SRPM found for $$pkg"; exit 1; }; \
			$(CONTAINER_RUN) mock -r $(MOCK_CHROOT) --rebuild $$srpm || exit 1; \
		fi; \
	done

FORCE_MOCK ?=
PROCEED_BUILD ?=
SKIP_MOCK ?=
SKIP_COPR ?=

pkg-full-cycle: ## Run full cycle with YAML report: spec → srpm → mock → copr (FEDORA_VERSION, PACKAGE, COPR_REPO, FORCE_MOCK, PROCEED_BUILD, SKIP_MOCK, SKIP_COPR)
	$(setup_volumes)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		COPR_REPO=$(COPR_REPO) \
		FORCE_MOCK=$(FORCE_MOCK) \
		PROCEED_BUILD=$(PROCEED_BUILD) \
		SKIP_MOCK=$(SKIP_MOCK) \
		SKIP_COPR=$(SKIP_COPR) \
		/work/.venv/bin/python3 scripts/full-cycle.py,Full cycle completed,Full cycle failed,$(MAKE_LOGS_DIR)/pkg-full-cycle)

pkg-copr: ## Submit PACKAGE (or all) SRPMs to Copr (requires COPR_REPO env var, runs in container)
	@test -n "$(COPR_REPO)" || (echo "Error: COPR_REPO is not set (e.g. export COPR_REPO=nett00n/hyprland)"; exit 1)
	$(setup_volumes)
	@for pkg in $(_PKGS); do \
		if [ -n "$(QUIET)" ]; then \
			_ld="$(MAKE_LOGS_DIR)/pkg-copr/$$pkg"; mkdir -p "$$_ld"; \
			if $(CONTAINER_RUN) spectool -g -R packages/$$pkg/$$pkg.spec >> "$$_ld/stdout.log" 2>> "$$_ld/stderr.log" && \
			   $(CONTAINER_RUN) rpmbuild -bs packages/$$pkg/$$pkg.spec >> "$$_ld/stdout.log" 2>> "$$_ld/stderr.log" && \
			   $(CONTAINER_RUN) copr-cli build $(COPR_REPO) ~/rpmbuild/SRPMS/$$pkg-*.src.rpm >> "$$_ld/stdout.log" 2>> "$$_ld/stderr.log"; then \
				echo $(HIGHLIGHT_PREFIX) "✓ copr: $$pkg"; \
			else \
				echo $(HIGHLIGHT_PREFIX) "✗ copr: $$pkg"; exit 1; \
			fi; \
		else \
			echo $(HIGHLIGHT_PREFIX) "sources: $$pkg"; \
			$(CONTAINER_RUN) spectool -g -R packages/$$pkg/$$pkg.spec || exit 1; \
			echo $(HIGHLIGHT_PREFIX) "srpm: $$pkg"; \
			$(CONTAINER_RUN) rpmbuild -bs packages/$$pkg/$$pkg.spec || exit 1; \
			echo $(HIGHLIGHT_PREFIX) "copr: $$pkg"; \
			$(CONTAINER_RUN) copr-cli build $(COPR_REPO) ~/rpmbuild/SRPMS/$$pkg-*.src.rpm || exit 1; \
		fi; \
	done

pkg-build-pop: ## Remove mock/copr build status for PKG=a,b (PKG="" removes all, requires confirmation)
	@if [ -z "$(PACKAGE)" ]; then \
		printf "Remove mock/copr status for ALL packages? [y/N] "; \
		read ans; \
		[ "$$ans" = "y" ] || [ "$$ans" = "Y" ] || { echo "Aborted."; exit 1; }; \
	fi; \
	PACKAGE="$(PACKAGE)" $(PYTHON) scripts/pkg-build-pop.py

stage-validate: ## Run validation stage (PACKAGE=<name>, runs in container)
	$(setup_volumes)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		/work/.venv/bin/python3 scripts/stage-validate.py,Validation stage passed,Validation stage failed,$(MAKE_LOGS_DIR)/stage-validate)

stage-spec: ## Run spec generation stage (PACKAGE=<name>, runs in container)
	$(setup_volumes)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		/work/.venv/bin/python3 scripts/stage-spec.py,Spec generation passed,Spec generation failed,$(MAKE_LOGS_DIR)/stage-spec)

stage-vendor: ## Run vendor tarball generation stage (Go packages only, PACKAGE=<name>, runs in container)
	$(setup_volumes)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		/work/.venv/bin/python3 scripts/stage-vendor.py,Vendor stage passed,Vendor stage failed,$(MAKE_LOGS_DIR)/stage-vendor)

stage-srpm: ## Run SRPM build stage (PACKAGE=<name>, runs in container)
	$(setup_volumes)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		/work/.venv/bin/python3 scripts/stage-srpm.py,SRPM stage passed,SRPM stage failed,$(MAKE_LOGS_DIR)/stage-srpm)

stage-mock: ## Run mock build stage (PACKAGE=<name>, FEDORA_VERSION, runs in container)
	$(setup_volumes)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		/work/.venv/bin/python3 scripts/stage-mock.py,Mock build stage passed,Mock build stage failed,$(MAKE_LOGS_DIR)/stage-mock)

stage-copr: ## Run Copr submission stage (PACKAGE=<name>, COPR_REPO required, runs in container)
	$(setup_volumes)
	$(call run_with_result,$(CONTAINER_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		COPR_REPO=$(COPR_REPO) \
		/work/.venv/bin/python3 scripts/stage-copr.py,Copr submission stage passed,Copr submission stage failed,$(MAKE_LOGS_DIR)/stage-copr)

pkg-log-analysis: ## Analyze build logs for PACKAGE and report actionable errors
	@test -n "$(PACKAGE)" || (echo "Error: PACKAGE is required (e.g. make pkg-log-analysis PKG=hyprland-plugins)"; exit 1)
	$(PYTHON) scripts/pkg-log-analysis.py $(PACKAGE)
