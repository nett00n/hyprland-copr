
Name:           hare-ev
Version:        0.26.0.0
Release:        2%{?dist}
Summary:        Event loop library for Hare
BuildArch:      noarch
License:        MPL-2.0
URL:            https://git.sr.ht/~sircmpwn/hare-ev
Source0:        https://git.sr.ht/~sircmpwn/hare-ev/archive/0.26.0.0.tar.gz#/hare-ev-0.26.0.0.tar.gz

BuildRequires:  make

Requires:       hare



%description
hare-ev is a third-party Hare library providing an event loop with timers, signals, child processes, and TCP/UDP/DNS clients and servers. It is installed as Hare source under the third-party module path.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1

%build
make %{?_smp_mflags}

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix}

%files
%doc README.md
%license COPYING
%{_prefix}/src/hare/third-party/ev

%package devel
Summary:        Development files for Event loop library for Hare
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hare-ev.

%files devel

%changelog
* Thu Nov 05 2026 nett00n <copr@nett00n.org> - 0.26.0.0-2

- Update to 0.26.0.0
