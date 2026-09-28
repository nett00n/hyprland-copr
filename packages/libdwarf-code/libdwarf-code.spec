
Name:           libdwarf-code
Version:        2.3.3
Release:        1%{?dist}
Summary:        Library to access DWARF debugging information
License:        LGPL 2.1
URL:            https://github.com/davea42/libdwarf-code
Source0:        https://github.com/davea42/libdwarf-code/archive/refs/tags/v2.3.3.tar.gz#/libdwarf-code-2.3.3.tar.gz

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
Tag:               v2.3.3
Commit:            1c267616a4c8dc46b3380f0be4296ff8767bdfbb

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
* Thu Sep 24 2026 nett00n <copr@nett00n.org> - 2.3.3-1

- Release=2.3.3
- -----BEGIN PGP SIGNATURE-----
- iQJKBAABCgA0FiEENP8JYcUMx44Ucot6i1vmhXJeCPEFAmq1S6cWHGRhdmVhNDJA
- bGludXhtYWlsLm9yZwAKCRCLW+aFcl4I8VqoD/9hbNLERhw26d0mE487kD/ZfP4D
- cf6mylOHZpWpaLNI+Cq535z25lNJDyUnNK9EmV0xH1EI73rAidmTUy/HpYVgSysq
- VVuZT+lC5B1dWVoRPSXh5fUM8pgp/1cLAx2tZxN8/NOVBOMw5cdCZ2v0dD12W4i9
- 1/A7N+i++DfE++b5oELAxWmTIQuMiapmHiO8jYLuJ3qElXTFfmsdM4KOcmFZo2Z2
- 7JDNfYY1xQG42/NPrgwkf2TrsF1Ne0iUFbu4TCnwHxmnkyL6NFy1sMDMRIMvsLmM
- zRxXI7TDtB1OOrvL0s5TNVUHCEbAWKNp99rhlvhlRdIkv8YWimgGV4CTY+vggqI+
- bXUlOeWmYymtfFTU00/rarWkbPC3LJQqKCqzVmpHoKXjhv02epz27hsfedKgdcyR
- ntGvZqD7yuXZiuIZuLG2lULGlrYtfTH+iyrJQCFoytmQgkz5badebSmehTFvMTLa
- 55geSji7585v9Qw0SY09zMcMuyLwH/bBsl1QAdEvDLLttHajy1mVgIFLSUzYSD2D
- li2of+f78ki8qs7uY5U1MBtEJ6/Whx1Jb+l9TAPqSbGFxo85lSzId4ja4XTTjyUM
- Us7wo/w8+ZTOgt71Bi+FoUfYt64mX2kjz5RSKDsnFlRcX7DUrwEX4PPdAZFvP/lJ
- dWF852wC1bFAxVH4Nw==
- =VgER
- -----END PGP SIGNATURE-----
