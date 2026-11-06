
Name:           hare-xml
Version:        0.25.2.0
Release:        2%{?dist}
Summary:        XML parser library for Hare
BuildArch:      noarch
License:        MPL-2.0
URL:            https://git.sr.ht/~sircmpwn/hare-xml
Source0:        https://git.sr.ht/~sircmpwn/hare-xml/archive/0.25.2.0.tar.gz#/hare-xml-0.25.2.0.tar.gz

BuildRequires:  make

Requires:       hare



%description
hare-xml is a third-party Hare library for parsing XML (format::xml). It is installed as Hare source under the third-party module path.

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
%{_prefix}/src/hare/third-party/format/xml

%package devel
Summary:        Development files for XML parser library for Hare
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hare-xml.

%files devel

%changelog
* Thu Nov 05 2026 nett00n <copr@nett00n.org> - 0.25.2.0-2

- Update to 0.25.2.0
