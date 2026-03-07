Name:           pyprland
Version:        3.1.1
Release:        %autorelease%{?dist}
Summary:        Scratchpads & many goodies for Hyprland [maintainer=@fdev31]
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

A plugin system that extends your graphical environment with features like scratchpads, dynamic popup nested menus, custom notifications, easy monitor settings and more

Think of it as a Gnome tweak tool for Hyprland, with options that can run on any desktop. With a fully plugin-based architecture, it's lightweight and easy to customize

%prep
%autosetup

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
* Sat Mar 07 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 3.1.1-%autorelease
- Update to 3.1.1
