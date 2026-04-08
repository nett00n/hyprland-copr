Name:           sndio
Version:        1.10.0
Release:        %autorelease%{?dist}
Summary:        Portable version of OpenBSD's lightweight audio & MIDI sub-system
License:        ISC
URL:            https://sndio.org/git/sndio
Source0:        https://sndio.org/sndio-%{version}.tar.gz

BuildRequires:  alsa-lib-devel
BuildRequires:  gcc
BuildRequires:  make

%description
Portable version of OpenBSD's lightweight audio & MIDI sub-system

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v1.10.0
Commit:            366b5c84d57c9ce73387c51ca48755d36e3fe3a7

Build dependencies:
alsa-lib-devel: 1.2.15.3
gcc: 16.0.1
make: 4.4.1

%prep
%autosetup -p1

%build
./configure --prefix=%{_prefix} --exec-prefix=%{_exec_prefix} --bindir=%{_bindir} --datadir=%{_datadir} --includedir=%{_includedir} --libdir=%{_libdir} --mandir=%{_mandir} --enable-alsa
%make_build

%install
%make_install

%files
%license LICENSE
%{_prefix}/bin/aucat
%{_prefix}/bin/midicat
%{_prefix}/bin/sndioctl
%{_prefix}/bin/sndiod
%{_prefix}/lib64/libsndio.so*
%{_prefix}/share/man/*/*.gz

%package devel
Summary:        Development files for Portable version of OpenBSD's lightweight audio & MIDI sub-system
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for sndio.

%files devel
%{_prefix}/include/sndio.h
%{_prefix}/lib64/pkgconfig/sndio.pc

%changelog
* Thu Aug 01 2024 nett00n <copr@nett00n.org> - 1.10.0-1
- Bump version to 1.10.0
