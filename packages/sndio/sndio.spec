
Name:           sndio
Version:        1.11.0
Release:        3%{?dist}
Summary:        Portable version of OpenBSD's lightweight audio & MIDI sub-system
License:        ISC
URL:            https://sndio.org/git/sndio
Source0:        https://sndio.org/sndio-1.11.0.tar.gz

BuildRequires:  alsa-lib-devel
BuildRequires:  gcc
BuildRequires:  libbsd-devel
BuildRequires:  make




%description
Portable version of OpenBSD's lightweight audio & MIDI sub-system

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v1.11.0
Commit:            3e700211b1ca4f3284dbc7493f73ef72793f349f

%prep
%autosetup -p1

%build
./configure --prefix=%{_prefix} --exec-prefix=%{_exec_prefix} --bindir=%{_bindir} --datadir=%{_datadir} --includedir=%{_includedir} --libdir=%{_libdir} --mandir=%{_mandir} --enable-alsa
%make_build

%install
%make_install

%files
%license LICENSE
%{_bindir}/aucat
%{_bindir}/midicat
%{_bindir}/sndioctl
%{_bindir}/sndiod
%{_libdir}/libsndio.so*
%{_mandir}/*/*.gz

%package devel
Summary:        Development files for Portable version of OpenBSD's lightweight audio & MIDI sub-system
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for sndio.

%files devel
%{_includedir}/sndio.h
%{_libdir}/pkgconfig/sndio.pc

%changelog
* Thu Oct 15 2026 nett00n <copr@nett00n.org> - 1.11.0-3

- sndiod: Don't discard the POLLERR bit.
