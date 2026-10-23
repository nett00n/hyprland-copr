"""Build system command templates."""

BUILD_SYSTEMS = {
    "cmake": ("%cmake\n%cmake_build", "%cmake_install"),
    "meson": ("%meson\n%meson_build", "%meson_install"),
    "autotools": ("%configure\n%make_build", "%make_install"),
    "configure": ("./configure\n%make_build", "%make_install"),
    "make": ("make %{?_smp_mflags}", "make install DESTDIR=%{buildroot}"),
    "python": ("%pyproject_wheel", "%pyproject_install"),
    "cargo": (
        "cargo build --offline --release",
        "install -Dm755 target/release/%{name} %{buildroot}%{_bindir}/%{name}",
    ),
    # #COPR-0027: Fedora zig-rpm-macros; --system zig-pkg makes the build offline
    "zig": ("%zig_build -Dpie", "%zig_install -Dpie"),
}
