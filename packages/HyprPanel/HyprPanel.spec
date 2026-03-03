%global commit 0e73df1dfedf0f6fa21ed0ae5e031b0663c8f400
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global commitdate 20260106
Name:           HyprPanel
Version:        0^20260106git0e73df1
Release:        %autorelease%{?dist}
Summary:        A Bar/Panel for Hyprland with extensive customizability.
License:        MIT
URL:            https://github.com/Jas-SinghFSU/HyprPanel
Source0:        %{url}/archive/%{commit}.tar.gz

BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  gcc-c++

%description
A panel built for Hyprland with Astal

%prep
%autosetup -n %{name}-%{commit}

%build
%meson
%meson_build

%install
%meson_install

%files
%license LICENSE
%doc README.md

%changelog
* Tue Mar 03 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0^20260106git0e73df1-%autorelease
- Update to 0^20260106git0e73df1
