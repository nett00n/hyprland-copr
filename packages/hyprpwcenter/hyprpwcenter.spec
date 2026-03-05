Name:           hyprpwcenter
Version:        0.1.2
Release:        %autorelease%{?dist}
Summary:        Volume management center for Hyprland
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpwcenter
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(libpipewire-0.3)
BuildRequires:  pkgconfig(hyprtoolkit)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(hyprutils)

%description
A GUI Pipewire control center built with hyprtoolkit.

%prep
%autosetup

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%license LICENSE
%doc README.md

%changelog
* Tue Feb 10 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.1.2-%autorelease
- An update adding a bunch of fixes and translations.
- pw: resend volume after unmute
- desktop: update name
- core: move to hyprutils logger
- ui: add layouting margin to text estimations
- feat: flaking hyprpwcenter by @Ciflire in https://github.com/hyprwm/hyprpwcenter/pull/5
- Properly handle sparse PipeWire profile indices for devices by @freevatar in https://github.com/hyprwm/hyprpwcenter/pull/8
- Handle node removal properly by @freevatar in https://github.com/hyprwm/hyprpwcenter/pull/10
- i18n: init by @vaxerski in https://github.com/hyprwm/hyprpwcenter/pull/15
- i18n: add Indonesian translations by @BlueBeret in https://github.com/hyprwm/hyprpwcenter/pull/16
- i18n: add Dutch translations  by @Pucas01 in https://github.com/hyprwm/hyprpwcenter/pull/17
- i18n: add Turkish translations by @Berikai in https://github.com/hyprwm/hyprpwcenter/pull/19
- i18n: add French translations by @luuumine in https://github.com/hyprwm/hyprpwcenter/pull/18
- Added Slovenian translation by @aljus7 in https://github.com/hyprwm/hyprpwcenter/pull/20
- Add Greek translations by @n00bady in https://github.com/hyprwm/hyprpwcenter/pull/21
- i18n: added italian translations by @alba4k in https://github.com/hyprwm/hyprpwcenter/pull/22
- i18n: add Finnish translations by @mintusmaximus in https://github.com/hyprwm/hyprpwcenter/pull/24
- i18n: add Hungarian translation by @therealmate in https://github.com/hyprwm/hyprpwcenter/pull/25
- Add Malayalam translations by @aka-nahal in https://github.com/hyprwm/hyprpwcenter/pull/27
- Serbian translations by @nnra6864 in https://github.com/hyprwm/hyprpwcenter/pull/29
- i18n: add Russian translations by @pngdrift in https://github.com/hyprwm/hyprpwcenter/pull/30
- i18n: add Spanish by @emersondivB0 in https://github.com/hyprwm/hyprpwcenter/pull/28
- i18n: add German translations by @d-hain in https://github.com/hyprwm/hyprpwcenter/pull/35
- i18n: add Norwegian Bokmål translations by @rxmlp in https://github.com/hyprwm/hyprpwcenter/pull/32
- i18n: add nepali translations by @pes18fan in https://github.com/hyprwm/hyprpwcenter/pull/36
- i18n: add Tatar translations by @pngdrift in https://github.com/hyprwm/hyprpwcenter/pull/37
- i18n: add arabic langauge (modern standard) by @AmmarHaddadi in https://github.com/hyprwm/hyprpwcenter/pull/31
- i18n: add Chinese Simplified translations by @betaksu in https://github.com/hyprwm/hyprpwcenter/pull/38
- fixed an issue where “100%” was displayed as “10…” by @FelipeFMA in https://github.com/hyprwm/hyprpwcenter/pull/40
- i18n: add Traditional Chinese (zh_TW) translations by @G36maid in https://github.com/hyprwm/hyprpwcenter/pull/42
- @Ciflire made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/5
- @freevatar made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/8
- @BlueBeret made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/16
- @Pucas01 made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/17
- @Berikai made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/19
- @luuumine made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/18
- @aljus7 made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/20
- @n00bady made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/21
- @mintusmaximus made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/24
- @therealmate made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/25
- @aka-nahal made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/27
- @nnra6864 made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/29
- @pngdrift made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/30
- @emersondivB0 made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/28
- @d-hain made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/35
- @rxmlp made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/32
- @pes18fan made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/36
- @AmmarHaddadi made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/31
- @betaksu made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/38
- @FelipeFMA made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/40
- @G36maid made their first contribution in https://github.com/hyprwm/hyprpwcenter/pull/42
- **Full Changelog**: https://github.com/hyprwm/hyprpwcenter/compare/v0.1.1...v0.1.2
