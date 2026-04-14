Name:           pyprland
Version:        3.1.1
Release:        %autorelease%{?dist}
Summary:        Scratchpads & many goodies for Hyprland
BuildArch:      noarch
License:        MIT
URL:            https://github.com/hyprland-community/pyprland
Source0:        %{url}/archive/refs/tags/%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  python3-devel
BuildRequires:  python3-hatchling
BuildRequires:  python3-pip
Requires:       python3-aiofiles
Requires:       python3-aiohttp
Requires:       python3-pillow
Requires:       qt6-qtdeclarative-devel
Requires:       qt6-qtquickcontrols2-devel

%description
Power up your desktop

A plugin system that extends your graphical
environment with features like scratchpads, dynamic popup nested menus,
custom notifications, easy monitor settings and moreThink of it as a Gnome
tweak tool for Hyprland, with options that can run on any desktop.
With a fully plugin-based architecture, it's lightweight and easy to
customize

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:

Build dependencies:
python3-devel: 3.14.4
python3-hatchling: 1.29.0
python3-pip: 26.0.1

%prep
%autosetup -p1

%build
python3 -m hatchling build -t wheel

%install
python3 -m pip install --no-deps --no-build-isolation --root %{buildroot} --prefix /usr dist/*.whl

%files
%doc README.md
%license LICENSE
%{_bindir}/pypr
%{_bindir}/pypr-quickstart
%{python3_sitelib}/pyprland
%{python3_sitelib}/pyprland-%{version}.dist-info

%changelog
* Mon Apr 13 2026 nett00n <copr@nett00n.org> - 3.1.1-1
- Update to 3.1.1
