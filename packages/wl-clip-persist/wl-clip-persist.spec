%global debug_package %{nil}

Name:           wl-clip-persist
Version:        0.5.0
Release:        3%{?dist}
Summary:        Keep Wayland clipboard even after programs close
License:        MIT
URL:            https://github.com/Linus789/wl-clip-persist
Source0:        https://github.com/Linus789/wl-clip-persist/archive/refs/tags/v0.5.0.tar.gz#/wl-clip-persist-0.5.0.tar.gz
Source1:        wl-clip-persist-0.5.0-vendor.tar.gz

BuildRequires:  cargo
BuildRequires:  rustc



%description
Keeps the Wayland clipboard populated after the application that owns the
selection exits. Wayland hands clipboard ownership to the source client, so
closing it normally loses the contents; wl-clip-persist watches the
data-control protocol, caches the selection in memory, and re-offers it on
the owner's behalf.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.5.0
Commit:            e26fde01c13922e3a65049dafb7d5adfbc52626e

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
%{_bindir}/wl-clip-persist

%changelog
* Tue Sep 23 2025 nett00n <copr@nett00n.org> - 0.5.0-3

- v0.5.0
