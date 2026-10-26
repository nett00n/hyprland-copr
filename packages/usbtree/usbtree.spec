%global debug_package %{nil}

Name:           usbtree
Version:        0.1.1
Release:        1%{?dist}
Summary:        Live USB device tree in your terminal
License:        MIT
URL:            https://github.com/gnomeria/usbtree
Source0:        https://github.com/gnomeria/usbtree/archive/refs/tags/v0.1.1.tar.gz#/usbtree-0.1.1.tar.gz
Source1:        usbtree-0.1.1-vendor.tar.gz

BuildRequires:  cargo
BuildRequires:  rustc




%description
Live USB device tree in your terminal. A Rust TUI built on nusb that lists
connected USB devices as a tree and updates as they come and go. It needs
neither root nor libusb.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.1.1
Commit:            fb3f94f6e6d41a52451b5b3b574d21679de3a2db

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
%{_bindir}/usbtree

%changelog
* Sat Aug 01 2026 nett00n <copr@nett00n.org> - 0.1.1-1

- chore(main): release 0.1.1 (#72)
- Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>
