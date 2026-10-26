%global debug_package %{nil}

Name:           rumno
Version:        0.1.4
Release:        2%{?dist}
Summary:        Media notification OSD for volume, brightness and music
License:        GPL-3.0-only
URL:            https://gitlab.com/ivanmalison/rumno
Source0:        https://gitlab.com/ivanmalison/rumno/-/archive/v0.1.4/rumno-v0.1.4.tar.gz#/rumno-0.1.4.tar.gz
Source1:        rumno-0.1.4-vendor.tar.gz

BuildRequires:  cargo
BuildRequires:  dbus-devel
BuildRequires:  gtk-layer-shell-devel
BuildRequires:  gtk3-devel
BuildRequires:  rustc




%description
Rumno is a lightweight media notification manager that shows volume, brightness
and music information as an on-screen display. A background daemon,
rumno-background, draws the notifications with GTK and layer-shell; the rumno
command talks to it over D-Bus. Start rumno-background from your compositor
config, for example `exec-once = rumno-background` in Hyprland.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.1.4
Commit:            8e41039179df4d875ac1547677762b47202befab

%prep
%autosetup -p1 -n %{name}-v%{version}
tar xf %{SOURCE1}

%build
cargo build --offline --release

%install
install -Dm755 target/release/rumno -t %{buildroot}%{_bindir}
install -Dm755 target/release/rumno-background -t %{buildroot}%{_bindir}

%files
%doc README.md
%license LICENSE
%{_bindir}/rumno
%{_bindir}/rumno-background

%changelog
* Sat May 23 2026 nett00n <copr@nett00n.org> - 0.1.4-2

- release: v0.1.4
