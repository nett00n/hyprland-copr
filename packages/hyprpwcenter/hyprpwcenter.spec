Name:           hyprpwcenter
Version:        0.1.2
Release:        %autorelease%{?dist}
Summary:        Volume management center for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpwcenter
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprgraphics-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(hyprtoolkit)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libpipewire-0.3)
BuildRequires:  pkgconfig(pixman-1)

%description
A GUI Pipewire control center built with hyprtoolkit

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
%{_prefix}/bin/hyprpwcenter
%{_prefix}/share/applications/hyprpwcenter.desktop

%changelog
* Tue Feb 10 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.2-%autorelease
- tag: v0.1.2, commit: 2ce8f3d174f2ae1c50c7dcc182d809a5ab33cad2
- version: bump to 0.1.2
