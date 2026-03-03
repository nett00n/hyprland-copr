Name:           gtk4-layer-shell
Version:        1.3.0
Release:        %autorelease%{?dist}
Summary:        FA library to create panels and other desktop components for Wayland using the Layer Shell protocol and GTK4
License:        MIT
URL:            https://github.com/wmww/gtk4-layer-shell
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  glib2-devel
BuildRequires:  gtk4-devel
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  gobject-introspection-devel
BuildRequires:  vala

%description
A library for using the Layer Shell and Session Lock Wayland protocols with GTK4. This Library is compatible with C, C++ and any language that supports GObject introspection files (Python, Vala, etc).

The Layer Shell protocol allows building desktop shell components such as panels, notifications and wallpapers. It can be used to anchor your windows to a corner or edge of the output, or stretch them across the entire output.

The Session Lock protocol allows building lock screens.

%prep
%autosetup

%build
%meson
%meson_build

%install
%meson_install

%files
%license LICENSE
%doc README.md
%{_prefix}/lib64/girepository-*/Gtk4LayerShell-*.typelib
%{_prefix}/lib64/girepository-*/Gtk4SessionLock-*.typelib
%{_prefix}/lib64/libgtk4-layer-shell.so*
%{_prefix}/lib64/liblayer-shell-preload.so

%package devel
Summary:        Development files for FA library to create panels and other desktop components for Wayland using the Layer Shell protocol and GTK4
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
* Wed Oct 29 2025 Vladimir nett00n Budylnikov <git@nett00n.org> - 1.3.0-%autorelease
- API: add `gtk_layer_set_respect_close()`/`gtk_layer_get_respect_close()`
- Fix: ignore `.closed` event by default (see [GTK3 LS #209](https://github.com/wmww/gtk-layer-shell/issues/209))
- Fix: use-after-free when screen lock fails (#106)
- Fix: don't remap unmapped windows on monitor change (#104)
- Tests: support optionally running under Valgrind
