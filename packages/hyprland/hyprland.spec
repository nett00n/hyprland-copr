
Name:           hyprland
Version:        0.55.4
Release:        6%{?dist}
Summary:        A Modern C++ Wayland Compositor
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/Hyprland
Source0:        https://github.com/hyprwm/Hyprland/archive/refs/tags/v0.55.4.tar.gz#/hyprland-0.55.4.tar.gz

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  glaze-devel
BuildRequires:  glslang-devel
BuildRequires:  hyprcursor-devel
BuildRequires:  hyprgraphics-devel
BuildRequires:  hyprland-protocols-devel
BuildRequires:  hyprlang-devel
BuildRequires:  hyprutils-devel
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  hyprwire-devel
BuildRequires:  lcms2-devel
BuildRequires:  lua-devel
BuildRequires:  luajit-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconf-pkg-config
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(gl)
BuildRequires:  pkgconfig(glesv2)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libinput)
BuildRequires:  pkgconfig(lua)
BuildRequires:  pkgconfig(luajit)
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
BuildRequires:  readline-devel
BuildRequires:  udis86-devel


Recommends:     uwsm

%description
Hyprland is a 100% independent, dynamic tiling Wayland compositor that
doesn't sacrifice on its looksIt provides the latest Wayland features,
is highly customizable, has all the eyecandy, the most powerful plugins,
easy IPC, much more QoL stuff than other compositors and more

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.55.4
Commit:            a0136d8c04687bb36eb8a28eb9d1ff92aea99704

%prep
%autosetup -p1 -n Hyprland-%{version}
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
Summary:        Development files for A Modern C++ Wayland Compositor
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprland.

%files devel
%{_includedir}/hyprland/
%{_prefix}/share/pkgconfig/hyprland.pc

%changelog
* Thu Jun 11 2026 nett00n <copr@nett00n.org> - 0.55.4-6

- [gha] Nix: update inputs
