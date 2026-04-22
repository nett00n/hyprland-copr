%global commit 019dac7a0560145d7a557005a21a7fe48ecabe3e
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global commitdate 20260421

Name:           hyprland-git
Version:        0.54.0^20260421git019dac7
Release:        %autorelease%{?dist}
Summary:        A Modern C++ Wayland Compositor [Built from latest commit, unstable]
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/Hyprland
Source0:        %{url}/archive/%{commit}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  glaze-devel
BuildRequires:  glslang-devel
BuildRequires:  hyprcursor-devel >= 0.1.11
BuildRequires:  hyprgraphics-devel >= 0.1.5
BuildRequires:  hyprland-protocols-devel >= 0.4.0
BuildRequires:  hyprlang-devel >= 0.6.4
BuildRequires:  hyprutils-devel >= 0.7.1
BuildRequires:  hyprwayland-scanner-devel >= 0.4.2
BuildRequires:  hyprwire-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(gl)
BuildRequires:  pkgconfig(glesv2)
BuildRequires:  pkgconfig(lcms2)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libinput)
BuildRequires:  pkgconfig(muparser)
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(pangocairo)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(re2)
BuildRequires:  pkgconfig(tomlplusplus)
BuildRequires:  pkgconfig(uuid)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(wayland-server)
BuildRequires:  pkgconfig(xcb-errors)
BuildRequires:  pkgconfig(xcb-icccm)
BuildRequires:  pkgconfig(xcursor)
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  udis86-devel


%description
hyprland-git
This package is build from latest commit and can be broken

Hyprland is a 100% independent, dynamic tiling Wayland compositor that
doesn't sacrifice on its looksIt provides the latest Wayland features,
is highly customizable, has all the eyecandy, the most powerful plugins,
easy IPC, much more QoL stuff than other compositors and more..

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

Build dependencies:
cmake: 4.3.0
gcc-c++: 16.0.1
glslang-devel: 16.2.0
hyprcursor-devel: 0.1.11
hyprgraphics-devel: 0.1.5
hyprland-protocols-devel: 0.4.0
hyprlang-devel: 0.6.4
hyprutils-devel: 0.7.1
hyprwayland-scanner-devel: 0.4.2
ninja-build: 1.13.2
udis86-devel: 1.7.2

%prep
%autosetup -p1 -n Hyprland-%{commit}
sed -i 's|^install(TARGETS start-hyprland)|target_include_directories(start-hyprland PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/../glaze-src/include")\ninstall(TARGETS start-hyprland)|' start/CMakeLists.txt

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_bindir}/hyprctl
%{_bindir}/hyprland
%{_bindir}/hyprpm
%{_bindir}/start-hyprland
%{_datadir}/bash-completion/completions/hyprctl
%{_datadir}/bash-completion/completions/hyprpm
%{_datadir}/fish/vendor_completions.d/hyprctl.fish
%{_datadir}/fish/vendor_completions.d/hyprpm.fish
%{_datadir}/hypr/
%{_datadir}/wayland-sessions/hyprland*.desktop
%{_datadir}/xdg-desktop-portal/hyprland-portals.conf
%{_datadir}/zsh/site-functions/_hyprctl
%{_datadir}/zsh/site-functions/_hyprpm
%{_mandir}/man1/hyprctl.1.gz
%{_mandir}/man1/Hyprland.1.gz
%{_prefix}/bin/Hyprland

%package devel
Summary:        Development files for A Modern C++ Wayland Compositor [Built from latest commit, unstable]
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprland-git.

%files devel
%{_includedir}/hyprland/
%{_prefix}/share/pkgconfig/hyprland.pc

%changelog
* Wed Apr 22 2026 nett00n <copr@nett00n.org> - 0.54.0^20260421git019dac7-1
- Update to 0.54.0^20260421git019dac7
