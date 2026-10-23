
Name:           waylock
Version:        1.6.0
Release:        3%{?dist}
Summary:        Small screenlocker for Wayland compositors
License:        ISC
URL:            https://github.com/ifreund/waylock
Source0:        https://github.com/ifreund/waylock/archive/refs/tags/v1.6.0.tar.gz#/waylock-1.6.0.tar.gz
Source1:        waylock-1.6.0-vendor.tar.gz

BuildRequires:  pam-devel
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  scdoc
BuildRequires:  zig
BuildRequires:  zig-rpm-macros



%description
Waylock is a small screenlocker for Wayland compositors implementing the ext-session-lock-v1 protocol, which is significantly more robust than earlier client-side locking approaches: a crash of the screenlocker does not unlock the session. Type your password and press Enter to unlock.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v1.6.0
Commit:            3f90742d4725cbd0516bb2a7304770c601641411

%prep
%autosetup -p1
tar xf %{SOURCE1}
sed -i 's/^const version = ".*";/const version = "%{version}";/' build.zig
sed -i 's/^\( *\)stdout.writeAll(\(.*\)) catch process.exit(1);$/&\n\1stdout.flush() catch process.exit(1);/' src/main.zig

%build
%zig_build -Dpie -Dllvm=true

%install
%zig_install -Dpie -Dllvm=true

%files
%config(noreplace) %{_sysconfdir}/pam.d/waylock
%doc README.md
%license LICENSE
%{_bindir}/waylock
%{_mandir}/man1/waylock.1*

%package devel
Summary:        Development files for Small screenlocker for Wayland compositors
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for waylock.

%files devel

%changelog
* Mon Apr 27 2026 nett00n <copr@nett00n.org> - 1.6.0-3

- waylock 1.6.0
- This release updates the required Zig version to 0.16.
- No changes to waylock's behavior are intended.
- Full changelog:
- Isaac Freund (3):
- build: bump version to 1.6.0-dev
- build: update to Zig 0.16
- build: bump version to 1.6.0
- -----BEGIN PGP SIGNATURE-----
- iQEzBAABCAAdFiEEX734TdInjbK4rYpSht7UAN39ehEFAmnvLyMACgkQht7UAN39
- ehH9igf/fKMPVy1etWOau+RaAASIL9o1AgeeBKDNB0HYt2IYwxxYiPT6LK9U8aac
- XKQXHS7nNy6ZDurSrovuQLH9MYgfIZ+wdYuteuL1F5VKc0Ne+zSJJDQB85+xEUt/
- qD+F6X8Skj0okJBik3D3kd9pOdjzzNa2C8Az01+3lv/RlfRuYoLiqqCPNGyWGijb
- rOr/+xW35o3UHYuTKGC+DjBi5sAVbdH/+F1ODUVNlwnOemFiHjVMzZ40IS+i/ZGe
- gJd/z9yvAIcZkCKUFiNwREEYdkz0IvPxQkFOtVQGRmjnDvzQ5FJHMODdKaJkR4Fm
- N1KS+H4q1mmC6pHEhUoN4pJf+5cMzQ==
- =CIKA
- -----END PGP SIGNATURE-----
