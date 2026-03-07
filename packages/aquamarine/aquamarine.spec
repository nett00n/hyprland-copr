Name:           aquamarine
Version:        0.10.0
Release:        %autorelease%{?dist}
Summary:        A very light linux rendering backend library
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/aquamarine
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(gl)
BuildRequires:  pkgconfig(glesv2)
BuildRequires:  pkgconfig(hwdata)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(libdisplay-info)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libinput)
BuildRequires:  pkgconfig(libseat)
BuildRequires:  pkgconfig(libudev)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)

%description
Aquamarine is a very light linux rendering backend library. It provides basic abstractions for an application to render on a Wayland session (in a window) or a native DRM session

It is agnostic of the rendering API (Vulkan/OpenGL) and designed to be lightweight, performant, and minimal

Aquamarine provides no bindings for other languages. It is C++-only

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
- tag: v0.10.0, commit: a20a0e67a33b6848378a91b871b89588d3a12573
- version: bump to 0.10.0
