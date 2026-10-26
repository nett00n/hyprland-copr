
Name:           hellwal
Version:        1.0.9
Release:        3%{?dist}
Summary:        Fast, extensible color palette generator
License:        MIT
URL:            https://github.com/danihek/hellwal
Source0:        https://github.com/danihek/hellwal/archive/refs/tags/v1.0.9.tar.gz#/hellwal-1.0.9.tar.gz

BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  stb_image-static




%description
Hellwal is a fast, extensible color palette generator written in C. It builds a
palette from an image or a theme file and renders templates (terminals, Hyprland,
GTK, bars and more) with it. Example templates and themes are installed in
/usr/share/hellwal.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v1.0.9
Commit:            97f033ad58c35b31bb2964e9ae55ac6f38527e69

%prep
%autosetup -p1
sed -i 's|#include "src/stb_image.h"|#include <stb/stb_image.h>|' hellwal.c
rm -f src/stb_image.h

%build
%make_build CFLAGS="%{optflags}" LDFLAGS="%{build_ldflags} -lm"

%install
install -Dpm0755 hellwal -t %{buildroot}%{_bindir}
install -Dpm0644 assets/hellwal-completion.bash %{buildroot}%{bash_completions_dir}/hellwal
install -Dpm0644 assets/hellwal.fish -t %{buildroot}%{fish_completions_dir}
mkdir -p %{buildroot}%{_datadir}/hellwal
cp -a templates themes %{buildroot}%{_datadir}/hellwal/

%files
%doc README.md
%license LICENSE
%{_bindir}/hellwal
%{_datadir}/hellwal/
%{bash_completions_dir}/hellwal
%{fish_completions_dir}/hellwal.fish

%changelog
* Fri Oct 23 2026 nett00n <copr@nett00n.org> - 1.0.9-3

- version:)
