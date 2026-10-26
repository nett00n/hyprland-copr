%global debug_package %{nil}

Name:           wpgtk
Version:        6.7.1
Release:        2%{?dist}
Summary:        GTK+ theme/wallpaper manager which uses pywal as its core
BuildArch:      noarch
License:        GPL-2.0-only
URL:            https://github.com/deviantfero/wpgtk
Source0:        https://github.com/deviantfero/wpgtk/archive/refs/tags/6.7.1.tar.gz#/wpgtk-6.7.1.tar.gz

BuildRequires:  desktop-file-utils
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel

Requires:       (pywal16 or pywal)
Requires:       gtk3
Requires:       procps-ng
Requires:       python3-gobject
Requires:       python3-pillow



%description
Wpgtk is a color-scheme, wallpaper and template manager with a GTK+ interface. It
uses pywal as its color generator and adds editing and saving of color schemes
together with their wallpapers, a template system that replaces keywords in any
text file when you change theme, and a GTK+ theme made for it. Works with either
pywal16 or pywal.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1
sed -i '/"pywal>=3.3.0",/d' pyproject.toml

%build
%pyproject_wheel

%install
%pyproject_install
install -Dpm0644 wpgtk/misc/wpgtk.desktop -t %{buildroot}%{_datadir}/applications
install -Dpm0644 completions/bash/wpg -t %{buildroot}%{bash_completions_dir}
install -Dpm0644 completions/zsh/_wpg -t %{buildroot}%{zsh_completions_dir}
%pyproject_save_files -L -a wpgtk

%files -f %{pyproject_files}
%doc README.md
%license LICENSE
%{_bindir}/wpg
%{_datadir}/applications/wpgtk.desktop
%{bash_completions_dir}/wpg
%{zsh_completions_dir}/_wpg

%changelog
* Mon Oct 26 2026 nett00n <copr@nett00n.org> - 6.7.1-2

- Update to 6.7.1
