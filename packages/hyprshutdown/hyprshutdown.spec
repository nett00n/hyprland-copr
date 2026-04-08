Name:           hyprshutdown
Version:        0.1.0
Release:        %autorelease%{?dist}
Summary:        A graceful shutdown utility for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprshutdown
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  aquamarine-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  glaze-devel
BuildRequires:  hyprgraphics-devel
BuildRequires:  hyprtoolkit-devel
BuildRequires:  hyprutils-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(pixman-1)

%description
A graceful shutdown/logout utility for Hyprland, which prevents apps from
crashing / dying unexpectedly

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.1.0
Commit:            9f18be9c4e1a484c65b22dd53280815dc79a5a56

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
%{_prefix}/bin/hyprshutdown

%changelog
* Tue Jan 27 2026 nett00n <copr@nett00n.org> - 0.1.0-1
- core: close socket FD on error paths and improve validation (#18)
- fix: close socket FD on error paths and improve validation
- HyprlandIPC.cpp:
- Close socket file descriptor on connect() and write() error paths
- Prevents FD leak when IPC operations fail
- AppState.cpp:
- Add validation for empty address in CApp::quit()
- Add validation for invalid PID before SIGTERM
- Fix error check logic: use else-if to avoid dereferencing error result
- refactor: use CScopeGuard for socket cleanup
