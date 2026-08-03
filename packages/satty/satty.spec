
Name:           satty
Version:        0.22.0
Release:        4%{?dist}
Summary:        Satty - Modern Screenshot Annotation
License:        MPL-2.0
URL:            https://github.com/gabm/satty
Source0:        https://github.com/gabm/satty/archive/refs/tags/v0.22.0.tar.gz#/satty-0.22.0.tar.gz
Source1:        satty-0.22.0-vendor.tar.gz

BuildRequires:  cargo
BuildRequires:  cargo-rpm-macros
BuildRequires:  desktop-file-utils
BuildRequires:  pkgconfig(cairo-gobject)
BuildRequires:  pkgconfig(epoxy)
BuildRequires:  pkgconfig(fontconfig)
BuildRequires:  pkgconfig(gtk4)
BuildRequires:  pkgconfig(libadwaita-1)
BuildRequires:  rustc



%description
Satty is a screenshot annotation tool inspired by Swappy and Flameshot.

Satty has been created to provide the following improvements over existing screenshot annotation tools:

    - very simple and easy to understand toolset (like Swappy)
    - fullscreen annotation mode and post shot cropping (like Flameshot)
    - extremely smooth rendering thanks to HW acceleration (OpenGL)
    - working on wlroots based compositors (Sway, Hyprland, River, ...)
    - minimal, modern looking UI, thanks to GTK and Adwaita
    - be a playground for new features (post window selection, post paint editing, ...)

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.22.0
Commit:            9f99065e4177820e965f5475503e5c3bdbd74e6a

%prep
%autosetup -p1 -n Satty-%{version}
tar xf %{SOURCE1}
tar xf %{SOURCE1}

%build
cargo build --offline --release

%install
install -Dm755 target/release/%{name} %{buildroot}%{_bindir}/%{name}

%files
%doc README.md
%license LICENSE
%{_bindir}/satty

%package devel
Summary:        Development files for Satty - Modern Screenshot Annotation
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for satty.

%files devel

%changelog
* Mon Aug 03 2026 nett00n <copr@nett00n.org> - 0.22.0-4

- Updating version to v0.22.0
