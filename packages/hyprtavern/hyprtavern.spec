%global commit 946aa84275af9c97773935b94c1f9cbd4dc3286b
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global commitdate 20260131
Name:           hyprtavern
Version:        0^20260131git946aa84
Release:        %autorelease%{?dist}
Summary:        A modern, simple and consistent session bus for IPC discovery.
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprtavern
Source0:        %{url}/archive/%{commit}.tar.gz
%global glaze_version 7.0.0
Source1:        https://github.com/stephenberry/glaze/archive/refs/tags/v7.0.0.tar.gz#/glaze-7.0.0.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(hyprwire)
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(uuid)
BuildRequires:  pkgconfig(openssl)
BuildRequires:  pkgconfig(hyprtoolkit)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  hyprwire-devel

%description
Let your apps meet and chat with each other.

A modern, simple and consistent session bus for IPC discovery.

Important

This project is still in early development. I'm working on adding docs and improving the protocol, but it's not set in stone yet.

%prep
%autosetup -n %{name}-%{commit}
tar xf %{SOURCE1}
mv glaze-7.0.0 glaze-src

%build
%cmake \
    -DFETCHCONTENT_FULLY_DISCONNECTED=ON \
    -DFETCHCONTENT_SOURCE_DIR_GLAZE=%{_builddir}/%{name}-%{commit}/glaze-src
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%doc README.md

%changelog
* Sun Mar 01 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0^20260131git946aa84-%autorelease
- Update to 0^20260131git946aa84
