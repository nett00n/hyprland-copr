%global debug_package %{nil}
Name:           cliphist
Version:        0.7.0
Release:        %autorelease%{?dist}
Summary:        Wayland clipboard manager with support for multimedia
License:        GPL-3.0-or-later
URL:            https://github.com/sentriz/cliphist
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
Source1:        %{name}-%{version}-vendor.tar.gz

BuildRequires:  golang
Requires:       wl-clipboard
Requires:       xdg-utils

%description
Clipboard history “manager” for Wayland
- Write clipboard changes to a history file.
- Recall history with dmenu, rofi, wofi (or whatever other picker you like).
- Both text and images are supported.
- Clipboard is preserved byte-for-byte.
    - Leading/trailing whitespace, no whitespace, or newlines are preserved.
    - Won’t break fancy editor selections like Vim wordwise, linewise, or block mode.
- No concept of a picker, only pipes.

Requires Go, wl-clipboard, xdg-utils (for image MIME inference)."

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.7.0
Commit:            efb61cb5b5a28d896c05a24ac83b9c39c96575f2

Build dependencies:
golang: 1.26.1

%prep
%autosetup -p1
tar xf %{SOURCE1}

%build
go build -v -ldflags='-s -w' -o %{name} .

%install
install -Dpm755 %{name} %{buildroot}%{_bindir}/%{name}

%files
%doc readme.md
%license LICENSE
%{_bindir}/cliphist

%package devel
Summary:        Development files for Wayland clipboard manager with support for multimedia
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for cliphist.

%files devel

%changelog
* Sat Oct 11 2025 nett00n <copr@nett00n.org> - 0.7.0-1
- chore: release 0.7.0 (#127)
- chore: release 0.7.0
- update CHANGELOG
