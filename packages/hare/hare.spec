%global debug_package %{nil}

Name:           hare
Version:        0.26.0.1
Release:        2%{?dist}
Summary:        Hare programming language driver and standard library
License:        MPL-2.0
URL:            https://git.sr.ht/~sircmpwn/hare
Source0:        https://git.sr.ht/~sircmpwn/hare/archive/0.26.0.1.tar.gz#/hare-0.26.0.1.tar.gz

BuildRequires:  binutils
BuildRequires:  harec
BuildRequires:  make
BuildRequires:  qbe
BuildRequires:  scdoc

Requires:       binutils
Requires:       harec
Requires:       qbe



%description
Hare is a systems programming language designed to be simple, stable, and robust. This package ships the hare build tool, haredoc and the standard library; it needs a harec of the same minor release.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1 -n hare-%{version}
cp configs/linux.mk config.mk

%build
make PREFIX=%{_prefix} ARCH=%{_arch} VERSION=%{version}

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix} ARCH=%{_arch} VERSION=%{version}
mkdir -p %{buildroot}%{_prefix}/src/hare/third-party

%files
%dir %{_prefix}/src/hare
%dir %{_prefix}/src/hare/third-party
%doc README.md
%license COPYING
%{_bindir}/hare
%{_bindir}/haredoc
%{_mandir}/man1/hare*.1*
%{_mandir}/man5/hare*.5*
%{_prefix}/src/hare/stdlib

%package devel
Summary:        Development files for Hare programming language driver and standard library
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hare.

%files devel

%changelog
* Thu Nov 05 2026 nett00n <copr@nett00n.org> - 0.26.0.1-2

- Update to 0.26.0.1
