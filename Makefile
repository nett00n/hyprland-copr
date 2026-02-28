FEDORA_VERSION  ?= 43
SUPPORTED        := 42 43 44 rawhide
IMAGE_NAME       := rpm-toolbox
PACKAGE      ?=

ifeq ($(FEDORA_VERSION),rawhide)
  MOCK_CHROOT := fedora-rawhide-x86_64
else
  MOCK_CHROOT := fedora-$(FEDORA_VERSION)-x86_64
endif

CONTAINER    := rpm$(FEDORA_VERSION)
TOOLBOX_RUN  := toolbox run -c $(CONTAINER)

ALL_PACKAGES := $(shell grep -oP '^\s{2}\K[a-z][a-z0-9_-]+(?=:)' packages.yaml)
_PKGS        := $(if $(PACKAGE),$(PACKAGE),$(ALL_PACKAGES))

PKG    ?=
PYTHON := .venv/bin/python3


.DEFAULT_GOAL := help
.PHONY: help setup-venv pkg-spec update-versions gen-report container-build container-enter container-clean container-all pkg-sources pkg-srpm pkg-mock pkg-copr pkg-full-cycle

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
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup-venv: ## Create .venv and install Python dependencies
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt

pkg-spec: ## Generate spec file(s) from packages.yaml (PKG=<name> for one package)
	$(PYTHON) scripts/gen-spec.py $(PKG)

update-versions: ## Fetch latest semver tags from submodules and update packages.yaml
	$(PYTHON) scripts/list-submodule-tags.py

gen-report: ## Render build-report.yaml into a Markdown status table (stdout)
	$(PYTHON) scripts/gen-report.py

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

pkg-full-cycle: ## Run full cycle with YAML report: spec → srpm → mock → copr (FEDORA_VERSION, PACKAGE, COPR_REPO, FORCE_MOCK)
	$(TOOLBOX_RUN) env \
		FEDORA_VERSION=$(FEDORA_VERSION) \
		MOCK_CHROOT=$(MOCK_CHROOT) \
		PACKAGE=$(PACKAGE) \
		COPR_REPO=$(COPR_REPO) \
		FORCE_MOCK=$(FORCE_MOCK) \
		python3 scripts/full-cycle.py

pkg-copr: pkg-srpm ## Submit PACKAGE (or all) SRPMs to Copr (requires COPR_REPO env var, runs in toolbox)
	@test -n "$(COPR_REPO)" || (echo "Error: COPR_REPO is not set (e.g. export COPR_REPO=nett00n/hyprland)"; exit 1)
	@for pkg in $(_PKGS); do \
		echo "==> copr: $$pkg"; \
		$(TOOLBOX_RUN) copr-cli build $(COPR_REPO) ~/rpmbuild/SRPMS/$$pkg-*.src.rpm || exit 1; \
	done
