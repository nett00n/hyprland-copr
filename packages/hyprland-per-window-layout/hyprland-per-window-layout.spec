
Name:           hyprland-per-window-layout
Version:        2.8.1
Release:        2%{?dist}
Summary:        Per-window keyboard layout daemon for Hyprland
License:        MIT
URL:            https://github.com/coffebar/hyprland-per-window-layout.git
Source0:        %{name}-%{version}.tar.gz
Source1:        %{name}-%{version}-vendor.tar.gz

BuildRequires:  cargo
BuildRequires:  rustc


%description
Per-window keyboard layout (language) for Hyprland wayland compositor.
Automatically switches keyboard layout based on the active window.

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
%doc README.md
%license LICENSE
%{_bindir}/%{name}

%changelog
* Tue May 19 2026 nett00n <copr@nett00n.org> - 2.8.1-2

- Update to 2.8.1
