Name:           hyprsunset
Version:        0.3.3
Release:        %autorelease%{?dist}
Summary:        An application to enable a blue-light filter on Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprsunset
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(hyprwayland-scanner)
BuildRequires:  pkgconfig(hyprland-protocols)

%description
An application to enable a blue-light filter on Hyprland

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
* Fri Oct 03 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.3.3-%autorelease
- A minor update with some fixes
- Fix systemd unit install directory by @peppapig450 in https://github.com/hyprwm/hyprsunset/pull/56
- fixes scheduling after suspend by @szwyngelu in https://github.com/hyprwm/hyprsunset/pull/59
- improve output debug message by @SaverinOnRails in https://github.com/hyprwm/hyprsunset/pull/60
- @peppapig450 made their first contribution in https://github.com/hyprwm/hyprsunset/pull/56
- @szwyngelu made their first contribution in https://github.com/hyprwm/hyprsunset/pull/59
- @SaverinOnRails made their first contribution in https://github.com/hyprwm/hyprsunset/pull/60
- **Full Changelog**: https://github.com/hyprwm/hyprsunset/compare/v0.3.2...v0.3.3
