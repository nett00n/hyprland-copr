
Name:           gtk4-layer-shell
Version:        1.3.0
Release:        11%{?dist}
Summary:        A library to create panels and other desktop components for Wayland using the Layer Shell protocol and GTK4
License:        MIT
URL:            https://github.com/wmww/gtk4-layer-shell
Source0:        https://github.com/wmww/gtk4-layer-shell/archive/refs/tags/v1.3.0.tar.gz#/gtk4-layer-shell-1.3.0.tar.gz

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
%{_libdir}/girepository-*/Gtk4LayerShell-*.typelib
%{_libdir}/girepository-*/Gtk4SessionLock-*.typelib
%{_libdir}/libgtk4-layer-shell.so*
%{_libdir}/liblayer-shell-preload.so

%package devel
Summary:        Development files for A library to create panels and other desktop components for Wayland using the Layer Shell protocol and GTK4
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for gtk4-layer-shell.

%files devel
%{_datadir}/gir-1.0/Gtk4LayerShell-1.0.gir
%{_datadir}/gir-1.0/Gtk4SessionLock-1.0.gir
%{_datadir}/vala/vapi/gtk4-layer-shell-0.deps
%{_datadir}/vala/vapi/gtk4-layer-shell-0.vapi
%{_includedir}/gtk4-layer-shell/gtk4-layer-shell.h
%{_includedir}/gtk4-layer-shell/gtk4-session-lock.h
%{_libdir}/pkgconfig/gtk4-layer-shell-0.pc

%changelog
* Wed Oct 29 2025 nett00n <copr@nett00n.org> - 1.3.0-11

- Release 1.3.0
