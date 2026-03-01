Name:           hypridle
Version:        0.1.7
Release:        %autorelease%{?dist}
Summary:        An idle management daemon for Hyprland

License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hypridle
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(hyprland-protocols)
BuildRequires:  pkgconfig(sdbus-c++)
BuildRequires:  hyprwayland-scanner-devel

%description
FIXME

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
/usr/bin/hypridle
/usr/lib/systemd/user/hypridle.service
/usr/share/hypr/hypridle.conf

%changelog
* Wed Aug 27 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.7-%autorelease
- A new release after a while of fixes.
- core: log when ScreenSaver interface is already registered by @PaideiaDilemma in https://github.com/hyprwm/hypridle/pull/133
- clang-tidy: fix some errors by @Honkazel in https://github.com/hyprwm/hypridle/pull/143
- feat: support `source` option for additional config files by @martabal in https://github.com/hyprwm/hypridle/pull/144
- core: guard against dbus logind interface not existing and check if on_(un)lock_cmd is empty by @PaideiaDilemma in https://github.com/hyprwm/hypridle/pull/151
- Add ability to ignore Wayland idle inhibitors by @ChrisHixon in https://github.com/hyprwm/hypridle/pull/155
- Ignore idle inhibition per-listener by @ChrisHixon in https://github.com/hyprwm/hypridle/pull/158
- nix: use gcc15 by @FridayFaerie in https://github.com/hyprwm/hypridle/pull/159
- Add a --help option by @ShyAssassin in https://github.com/hyprwm/hypridle/pull/160
- @martabal made their first contribution in https://github.com/hyprwm/hypridle/pull/144
- @ChrisHixon made their first contribution in https://github.com/hyprwm/hypridle/pull/155
- @FridayFaerie made their first contribution in https://github.com/hyprwm/hypridle/pull/159
- @ShyAssassin made their first contribution in https://github.com/hyprwm/hypridle/pull/160
- **Full Changelog**: https://github.com/hyprwm/hypridle/compare/v0.1.6...v0.1.7
