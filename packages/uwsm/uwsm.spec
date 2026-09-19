%global debug_package %{nil}

Name:           uwsm
Version:        0.27.0
Release:        2%{?dist}
Summary:        Universal Wayland Session Manager
License:        MIT
URL:            https://github.com/Vladimir-csp/uwsm
Source0:        https://github.com/Vladimir-csp/uwsm/archive/refs/tags/v0.27.0.tar.gz#/uwsm-0.27.0.tar.gz

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
Tag:               v0.27.0
Commit:            f82dece2cedf308c897513f093f45025fbfdda4f

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
* Tue Sep 15 2026 nett00n <copr@nett00n.org> - 0.27.0-2

- chore: Release 0.27.0 "Your Friendly Neighborhood Skynet"
- feat: editable export/cleanup lists
- feat: also use UWSM_DEBUG var to control debug
- fix: pre-check shell syntax before sourcing env scripts, discard a set of extensions, fixes #226
- fix(uwsm-app): cancel PIPE trap when triggered, fixes #222
- fix(uwsm-app): reap pipekiller before exec/exit (#225)
- fix(app-daemon): recover app-daemon when client dies mid-handshake (#223)
- fix(app-daemon): remove error flag in exception
- fix: remove deprecated UWSM_NO_TWEAKS
- fix: correct typos (#227)
