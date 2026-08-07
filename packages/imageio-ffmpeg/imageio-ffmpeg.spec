%global debug_package %{nil}

Name:           imageio-ffmpeg
Version:        0.6.0
Release:        8%{?dist}
Summary:        FFMPEG wrapper for Python
BuildArch:      noarch
License:        BSD-2-Clause
URL:            https://github.com/imageio/imageio-ffmpeg
Source0:        https://github.com/imageio/imageio-ffmpeg/archive/refs/tags/v0.6.0.tar.gz#/imageio-ffmpeg-0.6.0.tar.gz

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools

Requires:       ffmpeg-free


%description
FFMPEG wrapper for Python. Uses the system ffmpeg binary rather than the platform-specific binary that upstream normally bundles into its wheels.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Tag:               v0.6.0
Commit:            ae47d8028c237ca5507ceef1b843ee427b442887

%prep
%autosetup -p1

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l -a imageio_ffmpeg

%files -f %{pyproject_files}
%doc README.md
%license LICENSE

%changelog
* Thu Jan 16 2025 nett00n <copr@nett00n.org> - 0.6.0-8

- Bump version
