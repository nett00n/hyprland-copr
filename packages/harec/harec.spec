
Name:           harec
Version:        0.26.0
Release:        2%{?dist}
Summary:        Hare compiler
License:        GPL-3.0-or-later
URL:            https://git.sr.ht/~sircmpwn/harec
Source0:        https://git.sr.ht/~sircmpwn/harec/archive/0.26.0.tar.gz#/harec-0.26.0.tar.gz

BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  qbe

Requires:       qbe



%description
harec is the bootstrapping compiler for the Hare systems programming language. It compiles Hare source to QBE intermediate language; it is driven by the hare build tool.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1 -n harec-%{version}
cp configs/linux.mk config.mk

%build
make %{?_smp_mflags} PREFIX=%{_prefix} ARCH=%{_arch} VERSION=%{version} CFLAGS="%{optflags} -std=c11 -D_XOPEN_SOURCE=700 -Iinclude" LDFLAGS="%{build_ldflags}"

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix} ARCH=%{_arch} VERSION=%{version}

%files
%doc README.md
%license COPYING
%{_bindir}/harec

%package devel
Summary:        Development files for Hare compiler
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for harec.

%files devel

%changelog
* Thu Nov 05 2026 nett00n <copr@nett00n.org> - 0.26.0-2

- Update to 0.26.0
