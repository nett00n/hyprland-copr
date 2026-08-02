
Name:           libdwarf-code
Version:        2.3.2
Release:        1%{?dist}
Summary:        Library to access DWARF debugging information
License:        LGPL 2.1
URL:            https://github.com/davea42/libdwarf-code
Source0:        https://github.com/davea42/libdwarf-code/archive/refs/tags/v2.3.2.tar.gz#/libdwarf-code-2.3.2.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build



%description
Libdwarf has been focused for years on both providing access to DWARF2 through DWARF5 data in a portable way while also detecting and reporting if the DWARF is corrupted and avoiding run-time crashes or memory leakage regardless how corrupted the DWARF being read may be. The intent is to provide ABI independent access to DWARF data and ensure that data returned by the library is meaningful.

When the DWARF6 standard is released by the DWARF committee support will be added (as soon as reasonably possible) to libdwarf for all changes/additions while continuing to support previous versions.

Libdwarf reads files from disk, it does not read running programs or running shared objects.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v2.3.2
Commit:            af7b278c6aa2ae9daad94fb7f8bffdc0e9980993

%prep
%autosetup -p1

%build
%cmake -DBUILD_SHARED=ON -DBUILD_NON_SHARED=OFF
%cmake_build
cmake -B build-static -DBUILD_SHARED=OFF -DBUILD_NON_SHARED=ON -DPIC_ALWAYS=ON -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DBUILD_DWARFDUMP=OFF -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build-static --parallel %{_smp_build_ncpus}

%install
%cmake_install
install -m 644 build-static/src/lib/libdwarf/libdwarf.a %{buildroot}%{_libdir}/

%files
%doc README.md
%{_bindir}/dwarfdump
%{_datadir}/dwarfdump/dwarfdump.conf
%{_libdir}/libdwarf.so.*
%{_mandir}/man1/dwarfdump.1.gz

%package devel
Summary:        Development files for Library to access DWARF debugging information
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for libdwarf-code.

%files devel
%{_includedir}/dwarf.h
%{_includedir}/libdwarf.h
%{_libdir}/cmake/libdwarf/Findzstd.cmake
%{_libdir}/cmake/libdwarf/libdwarf-targets-noconfig.cmake
%{_libdir}/cmake/libdwarf/libdwarf-targets.cmake
%{_libdir}/cmake/libdwarf/libdwarfConfig.cmake
%{_libdir}/cmake/libdwarf/libdwarfConfigVersion.cmake
%{_libdir}/libdwarf.a
%{_libdir}/libdwarf.so
%{_libdir}/pkgconfig/libdwarf.pc

%changelog
* Tue Jul 07 2026 nett00n <copr@nett00n.org> - 2.3.2-1

- Release=2.3.2
- -----BEGIN PGP SIGNATURE-----
- iQJKBAABCgA0FiEENP8JYcUMx44Ucot6i1vmhXJeCPEFAmpNbdcWHGRhdmVhNDJA
- bGludXhtYWlsLm9yZwAKCRCLW+aFcl4I8d+xD/98p5qkw1nwyClxfgv5YgicrAKA
- /A2uWYaCGzu6SRnhGwQ/q6ofl2/95D1CuOnYgFR6pZUtAAYb8MySVDmhNEY4gexw
- qDDAfWZ2IT9jtDla35VN1CVsa8LKt1PeA4gMJDw0dx7D+8xEIP+V3cQshdSS2Cg+
- 0ozjdGE9ea6xptJRbe+4rMwNbHmxkmtiWdV5h9DNARi9hWs6L5R1+HzX6SRpa/qY
- B99QK9UNXazepq7PFPljUf+DoVpzRkEg3u3IY4qZmGzdc6dpIDC5bVv58Opn3cKt
- /r9dKf5ugHNW48fqE4otVQjThkbnrHNTaubR6HFcPkoh0g5Ec1X++TLK1DOFvQyk
- BKf3yKrBIaWhcKvdvoUDw6tlexq+ptsEksMt7UVogyrQmRaI0ahgB0kYShhx67oi
- egsK/Uf0HsqJagjhJPehQYkYgTdV33xsu4wQgdP2lxdVnRh7RakjVVoaSh4G3T7C
- n5AQoq8o3t5Q1fDEq/QXdJHEzIsTdZhpQ6oERCz0yLUwYGcUioDOEhIYBMASgUU5
- rjM8WCyt1yGcQ8hp95f4B5A0MbVVALTDEJ8R23gA00GYd8zqF7lWbitS6LbvmNup
- geehICCqhD9Vy52j1AsN9QL1QaPfrCRyU6US1HxIMIM5ab7g/1wZu3G3ApkQmUOc
- lBRf9z+LidYtkrPqAA==
- =igRZ
- -----END PGP SIGNATURE-----
