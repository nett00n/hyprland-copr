
Name:           swaylock-plugin
Version:        1.8.7
Release:        2%{?dist}
Summary:        Swaylock fork that can use a Wayland client as lock screen background
License:        MIT
URL:            https://github.com/mstoeckl/swaylock-plugin
Source0:        https://github.com/mstoeckl/swaylock-plugin/archive/refs/tags/v1.8.7.tar.gz#/swaylock-plugin-1.8.7.tar.gz

BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  pam-devel
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(gdk-pixbuf-2.0)
BuildRequires:  pkgconfig(libsystemd)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(wayland-scanner)
BuildRequires:  pkgconfig(wayland-server)
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  scdoc




%description
swaylock-plugin is a fork of swaylock, the screen locker for Wayland, that can use the output of a wayland client (such as a wallpaper program or an animated shader) as the lock screen background. It installs alongside swaylock under its own names.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v1.8.7
Commit:            117ed3fe7d68a6f579cac6ce7a1bf82ceddb54d0

%prep
%autosetup -p1

%build
%meson
%meson_build

%install
%meson_install

%files
%config(noreplace) %{_sysconfdir}/pam.d/swaylock-plugin
%doc README.md
%license LICENSE
%{_bindir}/swaylock-plugin
%{_bindir}/swaylock-sleep-watcher
%{_datadir}/bash-completion/completions/swaylock-plugin
%{_datadir}/fish/vendor_completions.d/swaylock-plugin.fish
%{_datadir}/zsh/site-functions/_swaylock-plugin
%{_mandir}/man1/swaylock-plugin.1*

%package devel
Summary:        Development files for Swaylock fork that can use a Wayland client as lock screen background
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for swaylock-plugin.

%files devel

%changelog
* Fri Jul 10 2026 nett00n <copr@nett00n.org> - 1.8.7-2

- build: bump version to 1.8.7
- This corresponds to swaylock 1.8.6.
