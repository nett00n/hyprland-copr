
Name:           libdwarf-code
Version:        2.3.1
Release:        10%{?dist}
Summary:        Library to access DWARF debugging information
License:        LGPL 2.1
URL:            https://github.com/davea42/libdwarf-code
Source0:        https://github.com/davea42/libdwarf-code/archive/refs/tags/v2.3.1.tar.gz#/libdwarf-code-2.3.1.tar.gz

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
Tag:               v2.3.1
Commit:            b5ef10c9df0f494596fd9d31e19048a3ed5f28ba

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
* Wed Mar 04 2026 nett00n <copr@nett00n.org> - 2.3.1-10

- Release=2.3.1
- -----BEGIN PGP SIGNATURE-----
- iQJKBAABCgA0FiEENP8JYcUMx44Ucot6i1vmhXJeCPEFAmmoxpwWHGRhdmVhNDJA
- bGludXhtYWlsLm9yZwAKCRCLW+aFcl4I8UWOD/45f49A2evZisc/FaDp7sdwuUgp
- CzC0rlojet1gLztcoHDBA/GtIG9Aeu9VseuDGxcB/z0DluWeY7r1mMsXjxz4eoDO
- Lw1J5DS0MN2DE3YJEOxqUvMXvxznX0oquqxvZes17reu5fyWggPMkIwlNM0RwzU6
- mt8GEpb27NCZm85S3sEQ824x0s4LwhBjJICsozcfMYFZnfDgYDefGqGAgbBSyhmw
- zBGNXbGmJeIM/nDhb3jzYFaNThDxjjuSj1xNuwGecIGXw5wTjKa7jlNuTmgAISql
- MSFGcJZZPFUN8LbLXNWCcFLks3+D/46HjraGp246YuszHNPxtrJEOp8Ly4JA9Z6t
- XRL/ysIzfep6wKUcgAcKSfXAZ7napR6rgHS73G9OA4nMNIJUK/uQg0QTmQoQ3Q0y
- nmkR5o7giXtPUIYidQTjwkYZ3jWBcF+zeeQd/7FnJfESnbDKFxVgN5gbkqU02ymb
- ZZNnBYwsyPJIU9xf/iokrkteJfCHVe6d6gPdAwn5QNlYlQltxGcwoHGvHAmLajJ+
- sgSnAelRYGJtdoAvQCGCl+LDpDAHQSEbs3p4Md2WKaNgbURrygacl5mHH1H19uJo
- GNphsPwp0xmjuYKJqAPFHt5uGuKriC1SE7kJaZ/H6wB/MtKC2N0wSJA2kcvJYk+O
- vCoUUPonDdeTx/Aubw==
- =3He8
- -----END PGP SIGNATURE-----
