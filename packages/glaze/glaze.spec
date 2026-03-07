%global debug_package %{nil}
Name:           glaze
Version:        7.1.0
Release:        %autorelease%{?dist}
Summary:        Extremely fast, in memory, JSON and reflection library for modern C++. BEVE, CBOR, CSV, MessagePack, TOML, YAML, EETF
License:        MIT
URL:            https://github.com/stephenberry/glaze
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  libasan
BuildRequires:  libubsan
BuildRequires:  ninja-build

%description
One of the fastest JSON libraries in the world. Glaze reads and writes from object memory, simplifying interfaces and offering incredible performance

%prep
%autosetup

%build
%cmake -DBUILD_TESTING=OFF
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE

%package devel
Summary:        Development files for Extremely fast, in memory, JSON and reflection library for modern C++. BEVE, CBOR, CSV, MessagePack, TOML, YAML, EETF
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for glaze.

%files devel
%{_prefix}/include/glaze/
%{_prefix}/share/glaze/*.cmake

%changelog
* Sat Feb 28 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 7.1.0-%autorelease
- tag: v7.1.0, commit: b71542bb16c9d793545062185d7fd9bedbc0b638
- v7.1.0 bump
