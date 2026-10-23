
Name:           swaylock-effects
Version:        1.7.0.0
Release:        2%{?dist}
Summary:        Swaylock fork with fancy effects (blur, clock, fade-in)
License:        MIT
URL:            https://github.com/jirutka/swaylock-effects
Source0:        https://github.com/jirutka/swaylock-effects/archive/refs/tags/v1.7.0.0.tar.gz#/swaylock-effects-1.7.0.0.tar.gz

BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  pam-devel
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(gdk-pixbuf-2.0)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(wayland-scanner)
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  scdoc



Provides:       swaylock
Conflicts:      swaylock

%description
swaylock-effects is a fork of swaylock, the screen locker for Wayland, with additional visual effects: screenshot-based lock screens with blur, scale, vignette, pixelate and greyscale effects, a clock indicator, and fade-in. It is a drop-in replacement for swaylock.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v1.7.0.0
Commit:            4f2234c6bca3ce80dce1dbf7407825a38d58103c

%prep
%autosetup -p1

%build
%meson
%meson_build

%install
%meson_install

%files
%config(noreplace) %{_sysconfdir}/pam.d/swaylock
%doc README.md
%license LICENSE
%{_bindir}/swaylock
%{_datadir}/bash-completion/completions/swaylock
%{_datadir}/fish/vendor_completions.d/swaylock.fish
%{_datadir}/zsh/site-functions/_swaylock
%{_mandir}/man1/swaylock.1*

%package devel
Summary:        Development files for Swaylock fork with fancy effects (blur, clock, fade-in)
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for swaylock-effects.

%files devel

%changelog
* Sat Dec 02 2023 nett00n <copr@nett00n.org> - 1.7.0.0-2

- v1.7.0.0
- -----BEGIN PGP SIGNATURE-----
- iQHFBAABCgAvFiEEv7UV5T50WUImhovnefKZsENajiMFAmVrZYYRHGpha3ViQGpp
- cnV0a2EuY3oACgkQefKZsENajiOVpQwAmHzn5c0CLoNVpYdcr/s0n3RAgicYa7ET
- b8HH0xnNqeQQ5SyLIZWMwjpTD8k2hex7kjQLujZ6MBOM8bLmXAz+m3H0zvGVcb39
- etxjkGjkhpioEBc+EyfJDeVzYBZA/mxBjSVw9QJyZQTBdlIQwhZ5CXlOx6PA44eL
- Foa2O5GopSep3iLF6SSY7iB9JeHeikcouFy3+c/C5/mhGGEJGbBM4xMuqfN4jOp0
- 0Ki2y9x0FDmGxK8GEnKqM9EbggeKJ/Hs+qZZkmEynicn+/vO7Qg5VNbrdXkV/YPd
- Irj6qvRMO+vFH7nkZ9sEy9TtBJT9HIpYNujuQHs016JQc8jPBXBYy8Qk7VriQdOs
- nGUW1gbqtl4nR2uH6ZhizTNoM6VR1sv6OloHdD+TXEZfJwDTQVfm/ggpL/8wKy6s
- aSYM+xP1dyy5NZA3I0rHJWCjwwuLoA/nlRycnW10H+QCmIs0VPUgCVve9aAwtf3p
- U0wScuzktKZVxbxS2yj5qHEn71u862aQ
- =GhLk
- -----END PGP SIGNATURE-----
