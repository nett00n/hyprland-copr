Name:           gtk4-layer-shell
Version:        1.3.0
Release:        %autorelease%{?dist}
Summary:        A library to create panels and other desktop components for Wayland using the Layer Shell protocol and GTK4
License:        MIT
URL:            https://github.com/wmww/gtk4-layer-shell
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  gcc-c++
BuildRequires:  glib2-devel
BuildRequires:  gobject-introspection-devel
BuildRequires:  gtk4-devel
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  vala

%description
A library for using the Layer Shell and Session Lock Wayland protocols
with GTK4. This Library is compatible with C, C++ and any language that
supports GObject introspection files (Python, Vala, etc)The Layer Shell
protocol allows building desktop shell components such as panels,
notifications and wallpapers. It can be used to anchor your windows
to a corner or edge of the output, or stretch them across the
entire outputThe Session Lock protocol allows building lock screens

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v1.3.0
Commit:            1c963c51514581c41b9bdae08cdf69171265cdda

Build dependencies:
gcc-c++: 16.0.1
glib2-devel: 2.88.0
gobject-introspection-devel: 1.86.0
gtk4-devel: 4.22.2
meson: 1.10.2
ninja-build: 1.13.2
vala: 0.56.19

%prep
%autosetup -p1

%build
%meson
%meson_build

%install
%meson_install

%files
%doc README.md
%license LICENSE
%{_prefix}/lib64/girepository-*/Gtk4LayerShell-*.typelib
%{_prefix}/lib64/girepository-*/Gtk4SessionLock-*.typelib
%{_prefix}/lib64/libgtk4-layer-shell.so*
%{_prefix}/lib64/liblayer-shell-preload.so

%package devel
Summary:        Development files for A library to create panels and other desktop components for Wayland using the Layer Shell protocol and GTK4
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for gtk4-layer-shell.

%files devel
%{_prefix}/include/gtk4-layer-shell/gtk4-layer-shell.h
%{_prefix}/include/gtk4-layer-shell/gtk4-session-lock.h
%{_prefix}/lib64/pkgconfig/gtk4-layer-shell-0.pc
%{_prefix}/share/gir-1.0/Gtk4LayerShell-1.0.gir
%{_prefix}/share/gir-1.0/Gtk4SessionLock-1.0.gir
%{_prefix}/share/vala/vapi/gtk4-layer-shell-0.deps
%{_prefix}/share/vala/vapi/gtk4-layer-shell-0.vapi

%changelog
* Wed Oct 29 2025 nett00n <copr@nett00n.org> - 1.3.0-1
- Release 1.3.0
