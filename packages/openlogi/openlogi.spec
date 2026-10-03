%global debug_package %{nil}

Name:           openlogi
Version:        0.8.11
Release:        1%{?dist}
Summary:        Local-first alternative to Logitech Options+ for HID++ devices
License:        MIT OR Apache-2.0
URL:            https://github.com/AprilNEA/OpenLogi
Source0:        https://github.com/AprilNEA/OpenLogi/archive/refs/tags/v0.8.11.tar.gz#/openlogi-0.8.11.tar.gz
Source1:        openlogi-0.8.11-vendor.tar.gz

BuildRequires:  cargo
BuildRequires:  clang-devel
BuildRequires:  gcc
BuildRequires:  rustc
BuildRequires:  systemd-rpm-macros



%description
OpenLogi is a local-first alternative to Logitech Options+ for HID++ devices: remap buttons, change DPI, and configure SmartShift from the command line or the background agent. No account and no telemetry; configuration lives in a plain TOML file.

This package ships the CLI and the background agent (a systemd user unit). Neither the GPUI desktop window nor the on-screen overlay is built: both depend on crates published only as git sources (gpui-kit, appicon), which cannot be vendored for offline COPR builds.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.8.11
Commit:            7a9d092a7dda0cb3b7ec18ada4424d681fca65ca

%prep
%autosetup -p1 -n OpenLogi-%{version}
sed -i -e '/crates\/openlogi-desktop/d' -e '/crates\/openlogi-overlay/d' -e '/"xtask"/d' Cargo.toml
sed -i '/^\[patch\./,/^$/d' Cargo.toml
rm -f Cargo.lock
tar xf %{SOURCE1}

%build
cargo build --offline --release -p openlogi -p openlogi-agent

%install
install -Dpm0755 target/release/openlogi -t %{buildroot}%{_bindir}
install -Dpm0755 target/release/openlogi-agent -t %{buildroot}%{_bindir}
install -Dpm0644 packaging/linux/udev/70-openlogi.rules -t %{buildroot}%{_prefix}/lib/udev/rules.d
install -Dpm0644 packaging/linux/systemd/openlogi-agent.service -t %{buildroot}%{_userunitdir}

%files
%doc README.md
%license LICENSE-APACHE
%license LICENSE-MIT
%{_bindir}/openlogi
%{_bindir}/openlogi-agent
%{_prefix}/lib/udev/rules.d/70-openlogi.rules
%{_userunitdir}/openlogi-agent.service

%package devel
Summary:        Development files for Local-first alternative to Logitech Options+ for HID++ devices
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for openlogi.

%files devel

%changelog
* Fri Oct 02 2026 nett00n <copr@nett00n.org> - 0.8.11-1

- chore: Release package openlogi version 0.8.11
