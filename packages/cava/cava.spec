%global debug_package %{nil}
%global _lto_cflags %{nil}
Name:           cava
Version:        0.10.7
Release:        %autorelease%{?dist}
Summary:        Cross-platform Audio Visualizer
License:        MIT
URL:            https://github.com/karlstav/cava
Source0:        %{url}/archive/refs/tags/%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  alsa-lib-devel
BuildRequires:  cmake
BuildRequires:  fftw-devel
BuildRequires:  gcc-c++
BuildRequires:  iniparser-devel
BuildRequires:  jack-audio-connection-kit-devel
BuildRequires:  make
BuildRequires:  ncurses-devel
BuildRequires:  ninja-build
BuildRequires:  pipewire-devel
BuildRequires:  portaudio-devel
BuildRequires:  pulseaudio-libs-devel
BuildRequires:  sdl2-compat-devel
BuildRequires:  sndio-devel

%description
Cross-platform Audio Visualizer E

Maintainer info:
Source repository: https://github.com/nett00n/hyprland-copr
COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/
Package info:

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

%changelog
* Fri Mar 27 2026 nett00n <copr@nett00n.org> - 0.10.7-%autorelease
- Update to 0.10.7
