%global debug_package %{nil}
%global _lto_cflags %{nil}

Name:           libcava-v0
Version:        0.10.7
Release:        8%{?dist}
Summary:        cava built as a shared library
License:        MIT
URL:            https://github.com/LukashonakV/cava
Source0:        https://github.com/LukashonakV/cava/archive/refs/tags/0.10.7.tar.gz#/libcava-v0-0.10.7.tar.gz

BuildRequires:  alsa-lib-devel
BuildRequires:  cmake
BuildRequires:  fftw-devel
BuildRequires:  gcc-c++
BuildRequires:  iniparser-devel
BuildRequires:  jack-audio-connection-kit-devel
BuildRequires:  libglvnd-devel
BuildRequires:  make
BuildRequires:  meson
BuildRequires:  ncurses-devel
BuildRequires:  ninja-build
BuildRequires:  pipewire-devel
BuildRequires:  portaudio-devel
BuildRequires:  pulseaudio-libs-devel
BuildRequires:  sdl2-compat-devel
BuildRequires:  sndio-devel



%description
cava built as a shared library, e.g. used by waybar.
Cava is not provided as an executable.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1 -n cava-%{version}

%build
%meson -Dbuild_target=lib -Dcava_font=false
%meson_build

%install
%meson_install

%files
%doc README.md
%license LICENSE
%{_libdir}/libcava.so.*

%package devel
Summary:        Development files for cava built as a shared library
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for libcava-v0.

%files devel
%{_includedir}/cava/
%{_libdir}/libcava.so
%{_libdir}/pkgconfig/libcava.pc

%changelog
* Wed Aug 05 2026 nett00n <copr@nett00n.org> - 0.10.7-8

- Update to 0.10.7
