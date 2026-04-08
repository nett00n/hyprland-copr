%global debug_package %{nil}
Name:           hyprshot
Version:        1.3.0
Release:        %autorelease%{?dist}
Summary:        Utility to easily take screenshots in Hyprland using your mouse
BuildArch:      noarch
License:        GPL-3.0-only
URL:            https://github.com/Gustash/Hyprshot
Source0:        %{url}/archive/refs/tags/%{version}.tar.gz

Requires:       /usr/bin/notify-send
Requires:       grim
Requires:       jq
Requires:       slurp
Requires:       wl-clipboard

%description
Hyprshot is an utility to easily take screenshot in Hyprland using your
mouseIt allows taking screenshots of windows, regions and monitors which
are savedto a folder of your choosing and copied to your clipboard

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

%prep
%autosetup -p1 -n Hyprshot-%{version}

%build
# nothing to compile

%install
install -Dpm0755 hyprshot -t %{buildroot}/%{_bindir}

%files
%doc README.md
%license LICENSE
%{_bindir}/hyprshot

%changelog
* Wed Apr 08 2026 nett00n <copr@nett00n.org> - 1.3.0-1
- Update to 1.3.0
