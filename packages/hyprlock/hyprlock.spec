Name:           hyprlock
Version:        0.9.2
Release:        %autorelease%{?dist}
Summary:        A gpu-accelerated screen lock for Hyprland

License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprlock
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(egl)
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(hyprgraphics)
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(pam)
BuildRequires:  pkgconfig(pangocairo)
BuildRequires:  pkgconfig(sdbus-c++)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-egl)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(xkbcommon)

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
%doc README.md
%license LICENSE
%{_bindir}/hyprlock
%{_datadir}/hypr/hyprlock.conf
%{_sysconfdir}/pam.d/hyprlock

%changelog
* Thu Oct 02 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.9.2-%autorelease
- A new patch release with some fixes :)
- Make detection of PAM library more portable by @tagattie in https://github.com/hyprwm/hyprlock/pull/840
- background: monitor transforms fixups by @PaideiaDilemma in https://github.com/hyprwm/hyprlock/pull/859
- core: remove dmabuf listeners after we are done with Screencopy by @PaideiaDilemma in https://github.com/hyprwm/hyprlock/pull/858
- renderer: move asyncResourceGatherer out of the renderer by @PaideiaDilemma in https://github.com/hyprwm/hyprlock/pull/863
- core: monitor replug workaround for nvidia by @PaideiaDilemma in https://github.com/hyprwm/hyprlock/pull/845
- lock-surface: remove redundant sendDestroy calls by @PaideiaDilemma in https://github.com/hyprwm/hyprlock/pull/868
- Refactor asset management to use shared_ptr by @davc0n in https://github.com/hyprwm/hyprlock/pull/870
- renderer: fix nvidia workaround by @PaideiaDilemma in https://github.com/hyprwm/hyprlock/pull/878
- @tagattie made their first contribution in https://github.com/hyprwm/hyprlock/pull/840
- **Full Changelog**: https://github.com/hyprwm/hyprlock/compare/v0.9.1...v0.9.2
