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

Build dependencies:
alsa-lib-devel: 1.2.15.3
cmake: 4.3.0
fftw-devel: 3.3.10
gcc-c++: 16.0.1
iniparser-devel: 4.2.6
jack-audio-connection-kit-devel: 1.9.22
make: 4.4.1
ncurses-devel: 6.6
ninja-build: 1.13.2
pipewire-devel: 1.6.3
portaudio-devel: 19.7.0
pulseaudio-libs-devel: 17.0
sdl2-compat-devel: 2.32.64

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
* Wed Apr 22 2026 nett00n <copr@nett00n.org> - 0.10.7-1
- Update to 0.10.7
