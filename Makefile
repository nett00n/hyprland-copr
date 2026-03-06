FEDORA_VERSION  ?= 43
SUPPORTED        := 42 43 44 rawhide
IMAGE_NAME       := rpm-toolbox

# Accept either PACKAGE or PKG; PACKAGE takes precedence
PACKAGE      ?=
PKG          ?=
PACKAGE      := $(or $(PACKAGE),$(PKG))

ifeq ($(FEDORA_VERSION),rawhide)
  MOCK_CHROOT := fedora-rawhide-x86_64
else
  MOCK_CHROOT := fedora-$(FEDORA_VERSION)-x86_64
endif

CONTAINER    := rpm$(FEDORA_VERSION)
TOOLBOX_RUN  := toolbox run -c $(CONTAINER)

ALL_PACKAGES := $(shell grep -oP '^\s{2}\K[a-zA-Z][a-zA-Z0-9_-]+(?=:)' packages.yaml)
_PKGS        := $(if $(PACKAGE),$(PACKAGE),$(ALL_PACKAGES))

PYTHON           := .venv/bin/python3
README_COPR      := docs/README.copr.md
COPR_INSTRUCTIONS := docs/INSTALL.copr.md


.DEFAULT_GOAL := help
.PHONY: help setup-venv lint fmt \
        pkg-spec update-versions list-tags scaffold-package \
        add-submodule add-package add-new \
        gen-report readme readme-github readme-copr copr-description normalize-paths sort-lists \
        container-build container-enter container-clean container-all \
        pkg-sources pkg-srpm pkg-mock pkg-copr pkg-full-cycle \
        stage-validate stage-spec stage-srpm stage-mock stage-copr

help: ## Show this help
	@echo "Usage: make [TARGET] [PACKAGE=<name>] [FEDORA_VERSION=<version>]"
	@echo ""
	@echo "  Supported versions : $(SUPPORTED)"
	@echo "  Default version    : 43"
	@echo ""
	@echo "  Examples:"
	@echo "    make pkg-srpm PACKAGE=hyprland"
	@echo "    make pkg-mock PACKAGE=hyprland FEDORA_VERSION=42"
	@echo "    make pkg-copr PACKAGE=hyprland"
	@echo "    make stage-spec stage-srpm stage-mock PACKAGE=hyprutils"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

setup-venv: ## Create .venv and install Python dependencies
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt

lint: ## Run ruff check on all scripts
	.venv/bin/ruff check scripts/

fmt: ## Run ruff format on all scripts
	.venv/bin/ruff format scripts/

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
	@_url=$$($(PYTHON) -c "import yaml; d=yaml.safe_load(open('packages.yaml')); print(d['packages']['$(PACKAGE)']['url'])"); \
	 _name=$$(basename $$_url); \
	 _org=$$(basename $$(dirname $$_url)); \
	 echo "==> adding submodule submodules/$$_org/$$_name"; \
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

readme-github: ## Generate README.md (GitHub format: table)
	$(PYTHON) scripts/gen-report.py --format github > ./README.md

readme-copr: ## Generate README.copr.md (COPR format: list)
	$(PYTHON) scripts/gen-report.py --format copr > ./docs/README.copr.md

readme: readme-github readme-copr ## Generate both README.md and docs/README.copr.md

# Update the COPR project description and instructions from markdown files.
# Requires: copr-cli installed + ~/.config/copr token
copr-description: $(README_COPR) $(COPR_INSTRUCTIONS) ## Push description and install instructions to COPR (COPR_REPO required)
	@test -n "$(COPR_REPO)" || (echo "Error: COPR_REPO is not set (e.g. export COPR_REPO=nett00n/hyprland)"; exit 1)
	$(TOOLBOX_RUN) copr-cli modify "$(COPR_REPO)" \
		--description "$$(cat $(README_COPR))" \
		--instructions "$$(cat $(COPR_INSTRUCTIONS))"
	@echo "Description updated → $(COPR_REPO)"

normalize-paths: ## Normalize paths in packages.yaml abs->macros (ARGS=--reverse or --dry-run)
	$(PYTHON) scripts/rpm-dir-prefixes-convert.py $(ARGS)

sort-lists: ## Sort build_requires/requires/files lists in packages.yaml (ARGS=--dry-run)
	$(PYTHON) scripts/sort-yaml-lists.py $(ARGS)

container-build: ## Build image and recreate toolbox container for FEDORA_VERSION
	podman build \
		--build-arg FEDORA_VERSION=$(FEDORA_VERSION) \
		-t $(IMAGE_NAME):$(FEDORA_VERSION) \
		-f Containerfile .
	toolbox rm --force $(CONTAINER)
	toolbox create \
		--image $(IMAGE_NAME):$(FEDORA_VERSION) $(CONTAINER)
	toolbox run \
		$(CONTAINER) \
		whoami

container-enter: ## Enter the toolbox shell interactively
	toolbox enter rpm$(FEDORA_VERSION)

container-clean: ## Remove toolbox container, image, and volumes for FEDORA_VERSION
	-toolbox rm --force $(CONTAINER)
	-podman rmi $(IMAGE_NAME):$(FEDORA_VERSION)

container-all: ## Build toolboxes for all supported Fedora versions
	@for v in $(SUPPORTED); do \
		echo "==> Fedora $$v"; \
		$(MAKE) container-build FEDORA_VERSION=$$v; \
	done

pkg-sources: ## Download sources for PACKAGE (or all) using spectool (runs in toolbox)
	@for pkg in $(_PKGS); do \
		echo "==> sources: $$pkg"; \
		$(TOOLBOX_RUN) spectool -g -R packages/$$pkg/$$pkg.spec || exit 1; \
	done

pkg-srpm: pkg-sources ## Build SRPM for PACKAGE (or all) (runs in toolbox)
	@for pkg in $(_PKGS); do \
		echo "==> srpm: $$pkg"; \
		$(TOOLBOX_RUN) rpmbuild -bs packages/$$pkg/$$pkg.spec || exit 1; \
	done

pkg-mock: pkg-srpm ## Build and test PACKAGE (or all) with mock for FEDORA_VERSION (runs in toolbox)
	@for pkg in $(_PKGS); do \
		echo "==> mock-build: $$pkg"; \
		srpm=$$(ls -t ~/rpmbuild/SRPMS/$$pkg-*.src.rpm 2>/dev/null | head -1); \
		test -n "$$srpm" || { echo "ERROR: no SRPM found for $$pkg"; exit 1; }; \
		$(TOOLBOX_RUN) mock -r $(MOCK_CHROOT) --rebuild $$srpm || exit 1; \
	done

FORCE_MOCK ?=
PROCEED_BUILD ?=

pkg-full-cycle: ## Run full cycle with YAML report: spec → srpm → mock → copr (FEDORA_VERSION, PACKAGE, COPR_REPO, FORCE_MOCK, PROCEED_BUILD)
	$(TOOLBOX_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		COPR_REPO=$(COPR_REPO) \
		FORCE_MOCK=$(FORCE_MOCK) \
		PROCEED_BUILD=$(PROCEED_BUILD) \
		python3 scripts/full-cycle.py

pkg-copr: pkg-srpm ## Submit PACKAGE (or all) SRPMs to Copr (requires COPR_REPO env var, runs in toolbox)
	@test -n "$(COPR_REPO)" || (echo "Error: COPR_REPO is not set (e.g. export COPR_REPO=nett00n/hyprland)"; exit 1)
	@for pkg in $(_PKGS); do \
		echo "==> copr: $$pkg"; \
		$(TOOLBOX_RUN) copr-cli build $(COPR_REPO) ~/rpmbuild/SRPMS/$$pkg-*.src.rpm || exit 1; \
	done

stage-validate: ## Run validation stage (PACKAGE=<name>, runs in toolbox)
	$(TOOLBOX_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		python3 scripts/stage-validate.py

stage-spec: ## Run spec generation stage (PACKAGE=<name>, runs in toolbox)
	$(TOOLBOX_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		python3 scripts/stage-spec.py

stage-srpm: ## Run SRPM build stage (PACKAGE=<name>, runs in toolbox)
	$(TOOLBOX_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		python3 scripts/stage-srpm.py

stage-mock: ## Run mock build stage (PACKAGE=<name>, FEDORA_VERSION, runs in toolbox)
	$(TOOLBOX_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		python3 scripts/stage-mock.py

stage-copr: ## Run Copr submission stage (PACKAGE=<name>, COPR_REPO required, runs in toolbox)
	$(TOOLBOX_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		PACKAGE=$(PACKAGE) \
		COPR_REPO=$(COPR_REPO) \
		python3 scripts/stage-copr.py
