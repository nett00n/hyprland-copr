
Name:           eww
Version:        0.6.0
Release:        3%{?dist}
Summary:        Elkowars Wacky Widgets is a standalone widget system made in Rust that allows you to implement your own, custom widgets in any window manager
License:        MIT
URL:            https://github.com/elkowar/eww
Source0:        https://github.com/elkowar/eww/archive/refs/tags/v0.6.0.tar.gz#/eww-0.6.0.tar.gz
Source1:        eww-0.6.0-vendor.tar.gz

BuildRequires:  atk-devel
BuildRequires:  cairo-devel
BuildRequires:  cairo-devel
BuildRequires:  cargo
BuildRequires:  dbus-devel
BuildRequires:  gdk-pixbuf2-devel
BuildRequires:  glib2-devel
BuildRequires:  gtk-layer-shell-devel
BuildRequires:  gtk3-devel
BuildRequires:  gtk3-devel
BuildRequires:  libdbusmenu-gtk3-devel
BuildRequires:  pango-devel
BuildRequires:  pango-devel
BuildRequires:  rustc


%description
Elkowars Wacky Widgets is a standalone widget system made in Rust that allows you to implement your own, custom widgets in any window manager

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.6.0
Commit:            d87c2fdbfdc012e76d229e4e9ea3325bc0f23e89

%prep
%autosetup -p1
tar xf %{SOURCE1}
tar xf %{SOURCE1}

%build
cargo build --offline --release

%install
install -Dm755 target/release/%{name} %{buildroot}%{_bindir}/%{name}

%files
%license LICENSE
%doc README.md
/usr/bin/eww

%package devel
Summary:        Development files for Elkowars Wacky Widgets is a standalone widget system made in Rust that allows you to implement your own, custom widgets in any window manager
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for eww.

%files devel

%changelog
* Sun Apr 21 2024 nett00n <copr@nett00n.org> - 0.6.0-3

- Release version 0.6.0
