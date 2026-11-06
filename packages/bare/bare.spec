
Name:           bare
Version:        0.3
Release:        2%{?dist}
Summary:        Lightweight vertical bar for Wayland compositors
License:        MIT
URL:            https://github.com/kupospelov/bare
Source0:        https://github.com/kupospelov/bare/archive/refs/tags/0.3.tar.gz#/bare-0.3.tar.gz
Source1:        bare-0.3-vendor.tar.gz

BuildRequires:  cargo
BuildRequires:  cargo-rpm-macros
BuildRequires:  pkgconfig(fontconfig)
BuildRequires:  rustc
BuildRequires:  scdoc




%description
bare is a lightweight vertical bar focused on maximizing useful screen space and minimizing resource usage. It has a built-in set of blocks (time, battery, cpu, memory, disk, volume, wireless, workspaces) and needs no compositor-specific IPC. The compositor must support ext-workspace-v1 and wlr-layer-shell-unstable-v1.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1
tar xf %{SOURCE1}

%build
cargo build --offline --release
scdoc < doc/bare.1.scd > doc/bare.1
scdoc < doc/bare.5.scd > doc/bare.5

%install
install -Dm755 target/release/bare -t %{buildroot}%{_bindir}
install -Dm644 doc/bare.1 -t %{buildroot}%{_mandir}/man1
install -Dm644 doc/bare.5 -t %{buildroot}%{_mandir}/man5

%files
%doc README.md
%license LICENSE
%{_bindir}/bare
%{_mandir}/man1/bare.1*
%{_mandir}/man5/bare.5*

%package devel
Summary:        Development files for Lightweight vertical bar for Wayland compositors
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for bare.

%files devel

%changelog
* Fri Nov 06 2026 nett00n <copr@nett00n.org> - 0.3-2

- Update to 0.3
