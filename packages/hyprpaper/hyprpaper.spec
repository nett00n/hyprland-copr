Name:           hyprpaper
Version:        0.8.3
Release:        %autorelease%{?dist}
Summary:        A blazing fast Wayland wallpaper utility

License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpaper
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  file-devel
BuildRequires:  gcc-c++
BuildRequires:  hyprgraphics-devel
BuildRequires:  hyprlang-devel
BuildRequires:  hyprtoolkit-devel
BuildRequires:  hyprutils-devel
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  hyprwire-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(gl)
BuildRequires:  pkgconfig(glesv2)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libjpeg)
BuildRequires:  pkgconfig(libpng)
BuildRequires:  pkgconfig(libwebp)
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  systemd-rpm-macros

%description
hyprpaper is a blazing fast Wayland wallpaper utility with IPC controls.

%prep
%autosetup

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_bindir}/hyprpaper
/usr/lib/systemd/user/hyprpaper.service

%changelog
* Thu Jan 29 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.8.3-%autorelease
- Another small patch release to fix some incorrectly applied wallpapers.
- matcher: fix matching in getSetting
- matcher: fix empty desc
- desc typo and keep state stable. by @ItsOhen in https://github.com/hyprwm/hyprpaper/pull/330
- @ItsOhen made their first contribution in https://github.com/hyprwm/hyprpaper/pull/330
- **Full Changelog**: https://github.com/hyprwm/hyprpaper/compare/v0.8.2...v0.8.3
