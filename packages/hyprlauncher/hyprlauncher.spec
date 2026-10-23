
Name:           hyprlauncher
Version:        0.1.7
Release:        2%{?dist}
Summary:        A multipurpose and versatile launcher / picker for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprlauncher
Source0:        https://github.com/hyprwm/hyprlauncher/archive/refs/tags/v0.1.7.tar.gz#/hyprlauncher-0.1.7.tar.gz

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprgraphics-devel
BuildRequires:  hyprlang-devel
BuildRequires:  hyprtoolkit-devel
BuildRequires:  hyprutils-devel
BuildRequires:  hyprwire-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(fontconfig)
BuildRequires:  pkgconfig(icu-uc)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libqalculate)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(xkbcommon)




%description
A multipurpose and versatile launcher / picker for Hyprland Features:

- Various providers: Desktop, Unicode, Emoji, Math, Font ..
- Speedy: Fast, multi-threaded fuzzy searching-
Daemon by default: instant opening of the launcher
- Entry frequency caching: commonly used entries appear above others
- Manual entry providing: make a simple selector from your own list

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.1.7
Commit:            d08efd580c782fbf52ec299f77cd6c0fef7ee3d5

%prep
%autosetup -p1

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_prefix}/bin/hyprlauncher

%changelog
* Tue Oct 20 2026 nett00n <copr@nett00n.org> - 0.1.7-2

- VERSION: bump to 0.1.7
