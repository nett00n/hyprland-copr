%global debug_package %{nil}

Name:           uwsm
Version:        0.26.6
Release:        1%{?dist}
Summary:        Universal Wayland Session Manager
License:        MIT
URL:            https://github.com/Vladimir-csp/uwsm
Source0:        https://github.com/Vladimir-csp/uwsm/archive/refs/tags/v0.26.6.tar.gz#/uwsm-0.26.6.tar.gz

BuildRequires:  gcc-c++
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  python3-dbus
BuildRequires:  python3-pyxdg
BuildRequires:  scdoc
BuildRequires:  systemd-rpm-macros


%description
Universal Wayland Session Manager

Provides a set of Systemd units and helpers to set up the environment and manage standalone Wayland compositor sessions.

Aside from environment setup/cleanup, it makes Systemd do most of the work and does not require any extra daemons running in background (except for a tiny waitpid process and a simple shell signal handler in the lightest case).

This setup provides robust session management, overridable compositor- and session-aware environment management, XDG autostart, bi-directional binding with login session, clean shutdown, solutions for a set of small but annoying gotchas of systemd session management.

For compositors this is an opportunity to offload: Systemd integration, session/XDG autostart management, Systemd/DBus activation environment interaction with its caveats.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.26.6
Commit:            469a39a5436f6c1086b4904d42227c03aee2e394

%prep
%autosetup -p1

%build
%meson
%meson_build

%install
%meson_install

%files
%doc README.md
%license LICENSE
%{_bindir}/uwsm
%{_datadir}/uwsm/modules/uwsm/
%{_datadir}/uwsm/plugins
%{_docdir}/uwsm/
%{_libexecdir}/uwsm/prepare-env.sh
%{_libexecdir}/uwsm/signal-handler.sh
%{_mandir}/man*/uwsm*.gz
%{_userunitdir}/app-graphical.slice
%{_userunitdir}/background-graphical.slice
%{_userunitdir}/session-graphical.slice
%{_userunitdir}/wayland-session-bindpid@.service
%{_userunitdir}/wayland-session-envelope@.target
%{_userunitdir}/wayland-session-pre@.target
%{_userunitdir}/wayland-session-shutdown.target
%{_userunitdir}/wayland-session-waitenv.service
%{_userunitdir}/wayland-session-xdg-autostart@.target
%{_userunitdir}/wayland-session@.target
%{_userunitdir}/wayland-wm-app-daemon.service
%{_userunitdir}/wayland-wm-env@.service
%{_userunitdir}/wayland-wm@.service

%package devel
Summary:        Development files for Universal Wayland Session Manager
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for uwsm.

%files devel

%changelog
* Sun Jun 28 2026 nett00n <copr@nett00n.org> - 0.26.6-1

- chore: Release 0.26.6
- fix(app): support compat /execarg_default: directives in xdg-terminals.list
- Also ignore unknown directives, fixes #219
