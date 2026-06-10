
Name:           aquamarine
Version:        0.12.0
Release:        2%{?dist}
Summary:        A very light linux rendering backend library
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/aquamarine
Source0:        https://github.com/hyprwm/aquamarine/archive/refs/tags/v0.12.0.tar.gz#/aquamarine-0.12.0.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprutils-devel
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(gl)
BuildRequires:  pkgconfig(glesv2)
BuildRequires:  pkgconfig(hwdata)
BuildRequires:  pkgconfig(libdisplay-info)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libinput)
BuildRequires:  pkgconfig(libseat)
BuildRequires:  pkgconfig(libudev)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)


%description
Aquamarine is a very light linux rendering backend library.
It provides basic abstractions for an application to render on a
Wayland session (in a window) or a native DRM sessionIt is agnostic of
the rendering API (Vulkan/OpenGL) and designed to be lightweight,
performant, and minimalAquamarine provides no bindings for other
languages. It is C++-only

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.12.0
Commit:            01eeae12aa171fc13869b530b0dbb918521fa401

%prep
%autosetup -p1

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
* Sat May 30 2026 nett00n <copr@nett00n.org> - 0.12.0-2

- version: bump to 0.12.0
