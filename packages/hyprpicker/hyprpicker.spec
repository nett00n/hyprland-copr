Name:           hyprpicker
Version:        0.4.6
Release:        %autorelease%{?dist}
Summary:        A wlroots-compatible Wayland color picker that does not suck
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/hyprpicker
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(pangocairo)
BuildRequires:  pkgconfig(libjpeg)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(hyprwayland-scanner)

%description
FIXME

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
* Tue Feb 10 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.4.6-%autorelease
- Another small update with a few fixes
- Exit with a specific code when the user has cancelled picking a color by @st0rmbtw in https://github.com/hyprwm/hyprpicker/pull/125
- Update README.md by @zedmakesense in https://github.com/hyprwm/hyprpicker/pull/126
- Made preview format match output format by @flashrun24 in https://github.com/hyprwm/hyprpicker/pull/123
- nix: use gcc15 by @FridayFaerie in https://github.com/hyprwm/hyprpicker/pull/131
- Notifications Support by @itsvlxd in https://github.com/hyprwm/hyprpicker/pull/130
- Fix flickering at top-left by @flashrun24 in https://github.com/hyprwm/hyprpicker/pull/133
- More  flexible positioning and scaling by @DreamMaoMao in https://github.com/hyprwm/hyprpicker/pull/138
- Change css example in man page to use hsl by @joelpeapen in https://github.com/hyprwm/hyprpicker/pull/139
- feat: add custom format decoration by @flashrun24 in https://github.com/hyprwm/hyprpicker/pull/142
- Add null check for cursor shape device by @pakhromov in https://github.com/hyprwm/hyprpicker/pull/145
- Feat: added keyboard movement by @flashrun24 in https://github.com/hyprwm/hyprpicker/pull/143
- @st0rmbtw made their first contribution in https://github.com/hyprwm/hyprpicker/pull/125
- @zedmakesense made their first contribution in https://github.com/hyprwm/hyprpicker/pull/126
- @FridayFaerie made their first contribution in https://github.com/hyprwm/hyprpicker/pull/131
- @itsvlxd made their first contribution in https://github.com/hyprwm/hyprpicker/pull/130
- @DreamMaoMao made their first contribution in https://github.com/hyprwm/hyprpicker/pull/138
- @joelpeapen made their first contribution in https://github.com/hyprwm/hyprpicker/pull/139
- @pakhromov made their first contribution in https://github.com/hyprwm/hyprpicker/pull/145
- **Full Changelog**: https://github.com/hyprwm/hyprpicker/compare/v0.4.5...v0.4.6
