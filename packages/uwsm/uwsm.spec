%global debug_package %{nil}

Name:           uwsm
Version:        0.26.4
Release:        2%{?dist}
Summary:        Universal Wayland Session Manager
License:        MIT
URL:            https://github.com/Vladimir-csp/uwsm
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

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
Tag:               v0.26.4
Commit:            3294dd3163bf9f2334b787b3cde5a14e56491404

Build dependencies:
gcc-c++: 16.0.1
meson: 1.10.2
ninja-build: 1.13.2
python3-dbus: 1.4.0
python3-pyxdg: 0.28
scdoc: 1.11.3
systemd-rpm-macros: 259.5

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
* Thu Feb 19 2026 nett00n <copr@nett00n.org> - 0.26.4-2

- chore: Release 0.26.4
- fix(may-start): move up login shell check
- Some people put startup construct into shell rc instead of profile. While this
- is not an optimal placement, it works. Don't clutter terminals with visible
- dealbreaker messages.
- fix: make CompGlobals.id_unit_string accessible to autoready fork again
