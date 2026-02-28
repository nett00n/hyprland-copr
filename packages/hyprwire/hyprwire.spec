Name:           hyprwire
Version:        0.3.0
Release:        %autorelease%{?dist}
Summary:        A fast and consistent wire protocol for IPC

License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprwire
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(libffi)
BuildRequires:  pkgconfig(pugixml)

%description
A fast and consistent wire protocol for IPC

%prep
%autosetup

%build
%cmake
%cmake_build

%install
%cmake_install

%files
/usr/bin/hyprwire-scanner
%{_libdir}/libhyprwire.so*
%license LICENSE

%package devel
Summary:        Development files for A fast and consistent wire protocol for IPC
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprwire.

%files devel
%{_includedir}/hyprwire/
%{_libdir}/cmake/hyprwire-scanner/
%{_libdir}/pkgconfig/hyprwire-scanner.pc
%{_libdir}/pkgconfig/hyprwire.pc

%changelog
* Wed Feb 04 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.3.0-%autorelease
- This is a big update with a lot of fixes and improvements for the upcoming tavern and beyond.
- core: enforce data types on the wire
- core: allow creating sockets from fds
- core: add a fd type
- generator: fix arr in s2c
- scanner: use const & for vecs to avoid copies
- scanner: avoid auto id
- protocol: add roundtrips
- core: fix empty arrays and wire arrays
- core: minor fixes
- parser: don't catch errors
- messages/generic: add fd error
- core: improve roundtrip
- server: fix sending fds
- core: fix creating sockets from fds
- server: fix crash on exit
- server: improve fd api
- server: return client on addClient
- server/client: add pid
- client: add isHandshakeDone()
- server: allow recursive mutex locks for pollmtx
- core/socket: fix parseFromFd having a potential data race
- core/client: fix version in bind protocol
- scanner: add name() to server object handlers
- message: avoid crash on fd array parsing for debug
- core: minor fixes
- docs: add wire docs
- add OpenBSD support by @jg1uaa in https://github.com/hyprwm/hyprwire/pull/6
- Include string_view header by @dylanetaft in https://github.com/hyprwm/hyprwire/pull/9
- server/socket: fix server socket destruction with attemptEmpty by @PointerDilemma in https://github.com/hyprwm/hyprwire/pull/7
- core/client: buffer pending data on waiting for object by @vaxerski in https://github.com/hyprwm/hyprwire/pull/10
- core: Fix serialization bug with unaligned pointer reads by @jimpo in https://github.com/hyprwm/hyprwire/pull/13
- core/message: Fix uninitialized global pointer by @jimpo in https://github.com/hyprwm/hyprwire/pull/12
- core/message: copy id instead of duplicating seq in m_data by @r0chd in https://github.com/hyprwm/hyprwire/pull/15
- core: integration fixes by @PointerDilemma in https://github.com/hyprwm/hyprwire/pull/14
- core: Add support for fd arrays by @r0chd in https://github.com/hyprwm/hyprwire/pull/16
- @jg1uaa made their first contribution in https://github.com/hyprwm/hyprwire/pull/6
- @dylanetaft made their first contribution in https://github.com/hyprwm/hyprwire/pull/9
- @PointerDilemma made their first contribution in https://github.com/hyprwm/hyprwire/pull/7
- @jimpo made their first contribution in https://github.com/hyprwm/hyprwire/pull/13
- @r0chd made their first contribution in https://github.com/hyprwm/hyprwire/pull/15
- **Full Changelog**: https://github.com/hyprwm/hyprwire/compare/v0.2.1...v0.3.0
