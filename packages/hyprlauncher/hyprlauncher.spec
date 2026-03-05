Name:           hyprlauncher
Version:        0.1.5
Release:        %autorelease%{?dist}
Summary:        A multipurpose and versatile launcher / picker for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprlauncher
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(hyprtoolkit)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(hyprwire)
BuildRequires:  pkgconfig(icu-uc)
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(fontconfig)
BuildRequires:  pkgconfig(libqalculate)

%description
A multipurpose and versatile launcher / picker for Hyprland
Features:

- Various providers: Desktop, Unicode, Emoji, Math, Font ...
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
%license LICENSE
%doc README.md

%changelog
* Sun Jan 04 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.5-%autorelease
- A small update with a massive improvement
- fuzzy: massively improve accuracy
- finders: increase the max amount of results
- i18n: add Latvian translation by @ocbwoy3 in https://github.com/hyprwm/hyprlauncher/pull/108
- @ocbwoy3 made their first contribution in https://github.com/hyprwm/hyprlauncher/pull/108
- **Full Changelog**: https://github.com/hyprwm/hyprlauncher/compare/v0.1.4...v0.1.5
