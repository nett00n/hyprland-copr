%global debug_package %{nil}

Name:           waycorner
Version:        0.2.3
Release:        3%{?dist}
Summary:        Hot corners for Wayland
License:        MIT
URL:            https://github.com/AndreasBackx/waycorner
Source0:        https://github.com/AndreasBackx/waycorner/archive/refs/tags/0.2.3.tar.gz#/waycorner-0.2.3.tar.gz
Source1:        waycorner-0.2.3-vendor.tar.gz

BuildRequires:  cargo
BuildRequires:  rustc




%description
Waycorner creates invisible anchors in the corners or along the edges of your
monitors and runs a command of your choice when the pointer enters or leaves
them. Configure it in ~/.config/waycorner/config.toml; the --preview flag
shows the active areas.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1
tar xf %{SOURCE1}

%build
cargo build --offline --release

%install
install -Dm755 target/release/%{name} %{buildroot}%{_bindir}/%{name}

%files
%doc CHANGELOG.md
%doc README.md
%license LICENSE
%{_bindir}/waycorner

%changelog
* Tue Nov 17 2026 nett00n <copr@nett00n.org> - 0.2.3-3

- Update to 0.2.3
