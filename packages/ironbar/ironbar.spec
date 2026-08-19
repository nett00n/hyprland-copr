
Name:           ironbar
Version:        0.19.0
Release:        13%{?dist}
Summary:        Customisable Wayland GTK4 bar written in Rust
License:        MIT
URL:            https://github.com/JakeStanger/ironbar
Source0:        https://github.com/JakeStanger/ironbar/archive/refs/tags/v0.19.0.tar.gz#/ironbar-0.19.0.tar.gz
Source1:        ironbar-0.19.0-vendor.tar.gz

BuildRequires:  cairo-gobject-devel
BuildRequires:  cargo
BuildRequires:  dh-autoreconf
BuildRequires:  gtk4-layer-shell-devel
BuildRequires:  libinput-devel
BuildRequires:  luajit-devel
BuildRequires:  pulseaudio-libs-devel
BuildRequires:  rust-gdk-pixbuf+default-devel
BuildRequires:  rust-gdk4-wayland-sys+default-devel
BuildRequires:  rust-glib-sys+default-devel
BuildRequires:  rust-graphene-rs-devel
BuildRequires:  rust-libdbus-sys+default-devel
BuildRequires:  rust-pango-devel
BuildRequires:  rustc



%description
Customisable and feature-rich GTK4 bar for Wayland compositors, written in Rust.
Ironbar is designed to support anything from a lightweight bar to a full desktop panel with ease.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.19.0
Commit:            607e28284b69f9e4089d8908a55aa770634224e3

%prep
%autosetup -p1
tar xf %{SOURCE1}

%build
cargo build --offline --release

%install
install -Dm755 target/release/%{name} %{buildroot}%{_bindir}/%{name}

%files
%doc README.md
%license LICENSE
%{_bindir}/ironbar

%package devel
Summary:        Development files for Customisable Wayland GTK4 bar written in Rust
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for ironbar.

%files devel

%changelog
* Sun May 17 2026 nett00n <copr@nett00n.org> - 0.19.0-13

- chore(release): v0.19.0
