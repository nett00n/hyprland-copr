"""Build system command templates."""

BUILD_SYSTEMS = {
    "cmake": ("%cmake\n%cmake_build", "%cmake_install"),
    "meson": ("%meson\n%meson_build", "%meson_install"),
    "autotools": ("%configure\n%make_build", "%make_install"),
    "configure": ("./configure\n%make_build", "%make_install"),
    "make": ("make %{?_smp_mflags}", "make install DESTDIR=%{buildroot}"),
    "python": ("%pyproject_build", "%pyproject_install"),
    "cargo": (
        "cargo build --offline --release",
        "install -Dm755 target/release/%{name} %{buildroot}%{_bindir}/%{name}",
    ),
}
