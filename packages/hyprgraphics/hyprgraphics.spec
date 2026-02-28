Name:           hyprgraphics
Version:        0.5.0
Release:        %autorelease%{?dist}
Summary:        Small C++ library for graphics utilities across the Hypr ecosystem

License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprgraphics
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pango-devel
BuildRequires:  pkgconfig(libjpeg)
BuildRequires:  pkgconfig(libpng)
BuildRequires:  pkgconfig(libwebp)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  file-devel
BuildRequires:  librsvg2-devel

%description
hyprgraphics is a small C++ library used across the Hypr* ecosystem for
graphics-related utilities such as image loading and color management.

%prep
%autosetup

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_libdir}/libhyprgraphics.so.*

%package devel
Summary:        Development files for Small C++ library for graphics utilities across the Hypr ecosystem
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprgraphics.

%files devel
%{_includedir}/hyprgraphics/
%{_libdir}/libhyprgraphics.so*
%{_libdir}/pkgconfig/hyprgraphics.pc

%changelog
* Sun Dec 28 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.5.0-%autorelease
- New release with a new ABI break
- image: cleanup format detection
- image/svg: implement embeded
- resource/image: add byte stream
- image: fix missing svg byte stream
- **Full Changelog**: https://github.com/hyprwm/hyprgraphics/compare/v0.4.0...v0.5.0
