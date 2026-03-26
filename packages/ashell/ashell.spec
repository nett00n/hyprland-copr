Name:           ashell
Version:        0.7.0
Release:        %autorelease%{?dist}
Summary:        A ready to go Wayland status bar for Hyprland and Niri
License:        MIT
URL:            https://github.com/MalpenZibo/ashell
Source0:        %{url}/archive/refs/tags/%{version}.tar.gz#/%{name}-%{version}.tar.gz
Source1:        %{name}-%{version}-vendor.tar.gz

BuildRequires:  cargo
BuildRequires:  make

%description
ashell is a ready to go Wayland status bar for Hyprland and Niri.

Feel free to fork this project and customize it for your needs or just open an issue to request a particular feature.

Maintainer info:
Source repository: https://github.com/nett00n/hyprland-copr
COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/
Package info:

%prep
%autosetup -p1
tar xf %{SOURCE1}
test -f .cargo/config.toml && echo "✓ .cargo/config.toml exists" && cat .cargo/config.toml || echo "✗ .cargo/config.toml NOT FOUND"

%build
CARGO_OFFLINE=1 make %{?_smp_mflags}

%install
CARGO_OFFLINE=1 make install DESTDIR=%{buildroot}

%files
%doc README.md
%license LICENSE

%package devel
Summary:        Development files for A ready to go Wayland status bar for Hyprland and Niri
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for ashell.

%files devel

%changelog
* Thu Mar 26 2026 nett00n <copr@nett00n.org> - 0.7.0-%autorelease
- Update to 0.7.0
