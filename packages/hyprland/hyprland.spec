%global upstream_commit_subject VERSION: bump to 0.57.2
%global upstream_commits 8015

Name:           hyprland
Version:        0.57.2
Release:        3%{?dist}
Summary:        A Modern C++ Wayland Compositor
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/Hyprland
Source0:        https://github.com/hyprwm/Hyprland/archive/refs/tags/v0.57.2.tar.gz#/hyprland-0.57.2.tar.gz

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  git-core
BuildRequires:  glaze-v7-devel
BuildRequires:  glslang-devel
BuildRequires:  hyprcursor-devel
BuildRequires:  hyprgraphics-devel
BuildRequires:  hyprland-protocols-devel
BuildRequires:  hyprlang-devel
BuildRequires:  hyprutils-devel
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  hyprwire-devel
BuildRequires:  lcms2-devel
BuildRequires:  libeis-devel
BuildRequires:  lua-devel
BuildRequires:  luajit-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconf-pkg-config
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(gl)
BuildRequires:  pkgconfig(glesv2)
BuildRequires:  pkgconfig(libcanberra)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libeis-1.0)
BuildRequires:  pkgconfig(libinput)
BuildRequires:  pkgconfig(lua)
BuildRequires:  pkgconfig(luajit)
BuildRequires:  pkgconfig(muparser)
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(pangocairo)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(re2)
BuildRequires:  pkgconfig(sdbus-c++)
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
Tag:               v0.57.2
Commit:            11cbc6c577b84ffb1edf4df3fc5b6128c3ae6947

%prep
%autosetup -p1 -n Hyprland-%{version}
%if 0%{?fedora} == 43
sed -i '/return (.* || std::ranges::starts_with(str_view, prefixes));/c\
auto check = [&](auto prefix) { return std::string(str_view.begin(), str_view.end()).starts_with(prefix); };\
return (... || check(prefixes));' src/helpers/MiscFunctions.cpp

sed -i -E 's/\b([A-Za-z_][A-Za-z0-9_]*)\.subview\(/std::string_view(\1).substr(/g' src/ipc/s1/S1.cpp

%endif

%build
export GIT_COMMIT_HASH=$(gzip -dc %{SOURCE0} | git get-tar-commit-id)
test -n "$GIT_COMMIT_HASH"
export GIT_TAG=v%{version}
export GIT_DIRTY=clean
export GIT_BRANCH=v%{version}
export GIT_COMMIT_MESSAGE="%{?upstream_commit_subject}"
export GIT_COMMITS=%{?upstream_commits}
export GIT_COMMIT_DATE="$(LC_ALL=C TZ=UTC date -d "$(tar -tvz --full-time --utc -f %{SOURCE0} | head -n1 | awk '{print $4" "$5}') UTC" '+%a %b %-d %H:%M:%S %Y')"
test -n "$GIT_COMMIT_DATE"
%cmake -Dglaze_DIR=%{_datadir}/glaze-v7
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_bindir}/hyprctl
%{_bindir}/hyprland
%{_bindir}/Hyprland
%{_bindir}/hyprpm
%{_bindir}/start-hyprland
%{_datadir}/bash-completion/completions/hyprpm
%{_datadir}/fish/vendor_completions.d/hyprpm.fish
%{_datadir}/hypr/
%{_datadir}/wayland-sessions/hyprland*.desktop
%{_datadir}/xdg-desktop-portal/hyprland-portals.conf
%{_datadir}/zsh/site-functions/_hyprpm
%{_libdir}/systemd/user/hyprland-session.target
%{_mandir}/man1/hyprctl.1.gz
%{_mandir}/man1/Hyprland.1.gz

%package devel
Summary:        Development files for A Modern C++ Wayland Compositor
Requires:       %{name} = %{version}-%{release}
Requires:       glslang-devel
Requires:       lua-devel

%description devel
Development files for hyprland.

%files devel
%{_datadir}/pkgconfig/hyprland.pc
%{_includedir}/hyprland/

%changelog
* Mon Nov 09 2026 nett00n <copr@nett00n.org> - 0.57.2-3

- VERSION: bump to 0.57.2
