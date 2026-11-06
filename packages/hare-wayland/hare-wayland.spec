%global debug_package %{nil}
%global commit fbcd672f0b2a5569cf2ca501f382daef8e49ff4f
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global commitdate 20260821

Name:           hare-wayland
Version:        0^20260821gitfbcd672
Release:        1%{?dist}
Summary:        Wayland client bindings and protocol scanner for Hare
License:        MPL-2.0
URL:            https://git.sr.ht/~sircmpwn/hare-wayland
Source0:        https://git.sr.ht/~sircmpwn/hare-wayland/archive/fbcd672f0b2a5569cf2ca501f382daef8e49ff4f.tar.gz

BuildRequires:  hare
BuildRequires:  hare-xml
BuildRequires:  make
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)

Requires:       hare
Requires:       hare-xml



%description
hare-wayland provides Wayland client bindings for Hare and hare-wlscanner, which generates Hare bindings from Wayland protocol XML files.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Commit:            fbcd672f0b2a5569cf2ca501f382daef8e49ff4f

%prep
%autosetup -p1 -n %{name}-%{commit}

%build
make PREFIX=%{_prefix}

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix}

%files
%doc README.md
%license COPYING
%{_bindir}/hare-wlscanner
%{_prefix}/src/hare/third-party/wayland

%package devel
Summary:        Development files for Wayland client bindings and protocol scanner for Hare
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hare-wayland.

%files devel

%changelog
* Sat Aug 08 2026 nett00n <copr@nett00n.org> - 0^20260821gitfbcd672-1

- Implement parsing "deprecated-since" attribute in entries.
- According to the Wayland documentation, entry elements can have the
- attribute "deprecated-since". It is for instance the case in the 1.26.0
- wayland release in wl_shm::error. This causes the current hare-wlscanner
- to abort when parsing wayland.xml.
