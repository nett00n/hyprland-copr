%global debug_package %{nil}
Name:           glaze
Version:        7.1.0
Release:        %autorelease%{?dist}
Summary:        Extremely fast, in memory, JSON and reflection library for modern C++. BEVE, CBOR, CSV, MessagePack, TOML, YAML, EETF
License:        MIT
URL:            https://github.com/stephenberry/glaze
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  libasan
BuildRequires:  libubsan

%description
One of the fastest JSON libraries in the world. Glaze reads and writes from object memory, simplifying interfaces and offering incredible performance.

%prep
%autosetup

%build
%cmake -DBUILD_TESTING=OFF
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%doc README.md

%package devel
Summary:        Development files for Extremely fast, in memory, JSON and reflection library for modern C++. BEVE, CBOR, CSV, MessagePack, TOML, YAML, EETF
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for glaze.

%files devel
/usr/include/glaze/
/usr/share/glaze/*.cmake

%changelog
* Sat Feb 28 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 7.1.0-%autorelease
- This release focuses on YAML maturity, networking reliability, container/generic behavior, and platform compatibility.
- > [!IMPORTANT]
- glz::generic now supports different underlying map types, but now defaults to a faster, ordered map, which preserves insertion order rather than sorting lexicographically. This ensures proper round tripping for unsorted JSON objects. See documentation for more details: https://stephenberry.github.io/glaze/generic-json
- YAML support received major hardening and coverage improvements, including parser correctness, conformance, roundtrip behavior, and generic integration.
- Related pull requests: [#2289](https://github.com/stephenberry/glaze/pull/2289), [#2293](https://github.com/stephenberry/glaze/pull/2293), [#2297](https://github.com/stephenberry/glaze/pull/2297), [#2298](https://github.com/stephenberry/glaze/pull/2298), [#2300](https://github.com/stephenberry/glaze/pull/2300), [#2302](https://github.com/stephenberry/glaze/pull/2302), [#2305](https://github.com/stephenberry/glaze/pull/2305), [#2317](https://github.com/stephenberry/glaze/pull/2317), [#2324](https://github.com/stephenberry/glaze/pull/2324), [#2335](https://github.com/stephenberry/glaze/pull/2335).
- HTTP/WebSocket behavior was improved across TLS support, handshake compatibility, CPU efficiency, and server internals.
- Related pull requests: [#2260](https://github.com/stephenberry/glaze/pull/2260), [#2284](https://github.com/stephenberry/glaze/pull/2284), [#2292](https://github.com/stephenberry/glaze/pull/2292), [#2321](https://github.com/stephenberry/glaze/pull/2321), [#2322](https://github.com/stephenberry/glaze/pull/2322), [#2323](https://github.com/stephenberry/glaze/pull/2323).
- Runtime generic behavior and ordered container support were improved, including insertion-order preservation and additional integer generic access support.
- Related pull requests: [#2318](https://github.com/stephenberry/glaze/pull/2318), [#2325](https://github.com/stephenberry/glaze/pull/2325), [#2334](https://github.com/stephenberry/glaze/pull/2334).
- Compatibility and CI coverage improved for MSVC and ARM targets, along with sanitizer/toolchain robustness fixes.
- Related pull requests: [#2273](https://github.com/stephenberry/glaze/pull/2273), [#2288](https://github.com/stephenberry/glaze/pull/2288), [#2303](https://github.com/stephenberry/glaze/pull/2303), [#2304](https://github.com/stephenberry/glaze/pull/2304), [#2309](https://github.com/stephenberry/glaze/pull/2309), [#2336](https://github.com/stephenberry/glaze/pull/2336), [#2337](https://github.com/stephenberry/glaze/pull/2337).
- Core quality improvements include SIMD/reflection work and correctness fixes around key handling and string conversion behavior.
- Related pull requests: [#2270](https://github.com/stephenberry/glaze/pull/2270), [#2281](https://github.com/stephenberry/glaze/pull/2281), [#2290](https://github.com/stephenberry/glaze/pull/2290), [#2329](https://github.com/stephenberry/glaze/pull/2329).
- https://github.com/stephenberry/glaze/compare/v7.0.2...v7.1.0
