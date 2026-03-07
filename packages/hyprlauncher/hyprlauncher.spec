Name:           hyprlauncher
Version:        0.1.5
Release:        %autorelease%{?dist}
Summary:        A multipurpose and versatile launcher / picker for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprlauncher
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprgraphics-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(fontconfig)
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(hyprtoolkit)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(hyprwire)
BuildRequires:  pkgconfig(icu-uc)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libqalculate)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(xkbcommon)

%description
A multipurpose and versatile launcher / picker for Hyprland
Features:

- Various providers: Desktop, Unicode, Emoji, Math, Font ..
- Speedy: Fast, multi-threaded fuzzy searching
- Daemon by default: instant opening of the launcher
- Entry frequency caching: commonly used entries appear above others
- Manual entry providing: make a simple selector from your own list

%prep
%autosetup

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
* Sun Jan 04 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.5-%autorelease
- tag: v0.1.5, commit: 086cfaa33541a347d040f8448ec4e4aff8f7f9bb
- version: bump to 0.1.5
