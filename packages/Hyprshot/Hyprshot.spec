%global debug_package %{nil}
Name:           Hyprshot
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
Hyprshot is an utility to easily take screenshot in Hyprland using your mouse.
It allows taking screenshots of windows, regions and monitors which are saved
to a folder of your choosing and copied to your clipboard.

%prep
%autosetup

%build


%install
install -Dpm0755 hyprshot -t %{buildroot}/%{_bindir}

%files
%doc README.md
%license LICENSE
%{_bindir}/hyprshot

%changelog
* Sun Mar 01 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 1.3.0-%autorelease
- Update to 1.3.0
