
Name:           waylock
Version:        1.7.0
Release:        1%{?dist}
Summary:        Small screenlocker for Wayland compositors
License:        ISC
URL:            https://github.com/ifreund/waylock
Source0:        https://github.com/ifreund/waylock/archive/refs/tags/v1.7.0.tar.gz#/waylock-1.7.0.tar.gz
Source1:        waylock-1.7.0-vendor.tar.gz

BuildRequires:  glibc-devel
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
Tag:               v1.7.0
Commit:            f2c695a42a23175945c2e21ad2ab1f8af7a1caec

%prep
%autosetup -p1
tar xf %{SOURCE1}
sed -i 's/^const version = ".*";/const version = "%{version}";/' build.zig
sed -i 's/^\( *\)stdout.writeAll(\(.*\)) catch process.exit(1);$/&\n\1stdout.flush() catch process.exit(1);/' src/main.zig

%build
printf 'include_dir=%{_includedir}\nsys_include_dir=%{_includedir}\ncrt_dir=%{_libdir}\nmsvc_lib_dir=\nkernel32_lib_dir=\ngcc_dir=\n' > zig-libc.txt
%zig_build -Dpie -Dllvm=true --libc zig-libc.txt

%install
%zig_install -Dpie -Dllvm=true --libc zig-libc.txt

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
* Tue Nov 10 2026 nett00n <copr@nett00n.org> - 1.7.0-1

- waylock 1.7.0
- This release updates the required Zig version to 0.17.1.
- The waylock PAM config is now installed to e.g. /usr/lib/pam.d
- by default. This matches the recommendations of the upstream
- PAM project.
- Also, Ctrl+Backspace is now supported to clear the password.
- Thank you to everyone who contributed!
- Full changelog:
- Hugo Osvaldo Barrera (1):
- build: install pam config into /usr/lib/pam.d/
- Isaac Freund (6):
- build: bump version to 1.7.0-dev
- build: fix default for -Dllvm build option
- cli: forgot to flush
- build: respect --prefix-lib-dir for pam.d/waylock
- build: update to Zig 0.17.1
- build: bump version to 1.7.0
- SimoneFelici (2):
- Fix version not showing
- Seat: clear password on Ctrl+Backspace
- -----BEGIN PGP SIGNATURE-----
- iQEzBAABCgAdFiEEX734TdInjbK4rYpSht7UAN39ehEFAmrzFnoACgkQht7UAN39
- ehHlmAf/b9Trrx5gw5kvEGaJ7dPvPd0QWY98OinXGyeCkd5f1SSoJmfmnKyK6cBB
- 4U1QVTFlu9/4uLCEH1XGl8qXbrNd+e77RedcHb7YQqhss/qegtKAIU7avfbgTJae
- N5tNbKFuXSi9KSCXMvlBlZaSYNIXi//+AEWZVGfCstf9/PGvGnRmnGqSTKjlYRSr
- fkUcXN3Imir8jI/237iGmflcnHrWLSPTa7cTZzR7pRefQKtCOpP07moLOKVgeoKd
- 4CSeuhsaDD9R0Zq+tgeO6PDSR5ZM/OPLxR4n0SSoO3yXkOe9LRw+Et7TpRhxHDpI
- qwDiduIYX/xJnqtnhrN4QyrOlWoAvg==
- =ytDY
- -----END PGP SIGNATURE-----
