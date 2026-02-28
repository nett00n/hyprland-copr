Name:           aquamarine
Version:        0.10.0
Release:        %autorelease%{?dist}
Summary:        A very light linux rendering backend library

License:        BSD-3-Clause
URL:            https://github.com/hyprwm/aquamarine
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  pkgconfig(libseat)
BuildRequires:  pkgconfig(libinput)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(libudev)
BuildRequires:  pkgconfig(libdisplay-info)
BuildRequires:  pkgconfig(hwdata)
BuildRequires:  pkgconfig(glesv2)
BuildRequires:  pkgconfig(gl)

%description
Aquamarine is a very light linux rendering backend library. It provides basic abstractions for an application to render on a Wayland session (in a window) or a native DRM session.

It is agnostic of the rendering API (Vulkan/OpenGL) and designed to be lightweight, performant, and minimal.

Aquamarine provides no bindings for other languages. It is C++-only.

%prep
%autosetup

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_libdir}/libaquamarine.so*
%license LICENSE

%package devel
Summary:        Development files for A very light linux rendering backend library
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for aquamarine.

%files devel
%{_includedir}/aquamarine/
%{_libdir}/pkgconfig/aquamarine.pc

%changelog
* Sun Nov 23 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.10.0-%autorelease
- A new ABI-breaking release.
- wayland: send commit after frame
- backend: implement hyprutils' cli::logger
- rendernode: dont bother finding one on evdi by @gulafaran in https://github.com/hyprwm/aquamarine/pull/214
- Ensure disconnect called for removed connectors by @jsierant in https://github.com/hyprwm/aquamarine/pull/215
- minor renderer changes by @gulafaran in https://github.com/hyprwm/aquamarine/pull/216
- prevent use-after-free during DRM backend shutdown by @andresilva in https://github.com/hyprwm/aquamarine/pull/218
- @jsierant made their first contribution in https://github.com/hyprwm/aquamarine/pull/215
- **Full Changelog**: https://github.com/hyprwm/aquamarine/compare/v0.9.5...v0.10.0
