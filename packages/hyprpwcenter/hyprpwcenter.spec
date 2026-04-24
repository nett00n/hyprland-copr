
Name:           hyprpwcenter
Version:        0.1.2
Release:        2%{?dist}
Summary:        Volume management center for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpwcenter
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprgraphics-devel >= 0.1.5
BuildRequires:  hyprtoolkit-devel
BuildRequires:  hyprutils-devel >= 0.7.1
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libpipewire-0.3)
BuildRequires:  pkgconfig(pixman-1)


%description
A GUI Pipewire control center built with hyprtoolkit

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.1.2
Commit:            2ce8f3d174f2ae1c50c7dcc182d809a5ab33cad2

Build dependencies:
cmake: 4.3.0
gcc-c++: 16.0.1
hyprgraphics-devel: 0.1.5
hyprutils-devel: 0.7.1
ninja-build: 1.13.2

%prep
%autosetup -p1

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_prefix}/bin/hyprpwcenter
%{_prefix}/share/applications/hyprpwcenter.desktop

%changelog
* Tue Feb 10 2026 nett00n <copr@nett00n.org> - 0.1.2-2

- version: bump to 0.1.2
