%global debug_package %{nil}
%global commit 76039750623825172fbee93adae8bb48d4ad36ad
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global commitdate 20260628

Name:           rustlock
Version:        0^20260628git7603975
Release:        3%{?dist}
Summary:        Wayland screen locker with effects, a Rust port of swaylock-effects
License:        GPL-3.0-or-later
URL:            https://github.com/JorySeverijnse/rustlock
Source0:        https://github.com/JorySeverijnse/rustlock/archive/76039750623825172fbee93adae8bb48d4ad36ad.tar.gz
Source1:        rustlock-0^20260628git7603975-vendor.tar.gz

BuildRequires:  cargo
BuildRequires:  clang-devel
BuildRequires:  dbus-devel
BuildRequires:  pam-devel
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(cairo-gobject)
BuildRequires:  pkgconfig(gdk-pixbuf-2.0)
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gobject-2.0)
BuildRequires:  pkgconfig(pangocairo)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  rustc




%description
Rustlock is a Wayland screen locker written in Rust, a port of swaylock-effects. It
uses the ext-session-lock protocol and PAM authentication, and can blur, pixelate or
swirl the screenshot behind the lock, with several ring shapes, a grace period and
optional WiFi, Bluetooth, battery and media indicators.

Maintainer info:

Source repository: https://github.com/nett00n/hyprland-copr

COPR repository:   https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/

Package info:
Commit:            76039750623825172fbee93adae8bb48d4ad36ad

%prep
%autosetup -p1 -n %{name}-%{commit}
tar xf %{SOURCE1}

%build
cargo build --offline --release

%install
install -Dm755 target/release/rustlock -t %{buildroot}%{_bindir}
install -Dm644 pam.d/rustlock -t %{buildroot}%{_sysconfdir}/pam.d
mkdir -p %{buildroot}%{bash_completions_dir} %{buildroot}%{fish_completions_dir} %{buildroot}%{zsh_completions_dir}
target/release/rustlock --completions bash > %{buildroot}%{bash_completions_dir}/rustlock
target/release/rustlock --completions fish > %{buildroot}%{fish_completions_dir}/rustlock.fish
target/release/rustlock --completions zsh > %{buildroot}%{zsh_completions_dir}/_rustlock

%files
%config(noreplace) %{_sysconfdir}/pam.d/rustlock
%doc README.md
%license LICENSE
%{_bindir}/rustlock
%{bash_completions_dir}/rustlock
%{fish_completions_dir}/rustlock.fish
%{zsh_completions_dir}/_rustlock

%changelog
* Sun Jun 28 2026 nett00n <copr@nett00n.org> - 0^20260628git7603975-3

- refactor: changed effects, add shell completions
- Extract all apply_* effect methods from screenshot.rs into dedicated
- src/effects.rs (blur, vignette, pixelate, swirl) — screenshot.rs
- Rewrite apply_blur: replace broken fastblur::gaussian_blur (horizontal-
- only box blur, backbuf dropped) with correct inline two-pass sliding-
- window box blur operating directly on Cairo surface bytes — ~10×
- faster, no ImageBuffer round-trip, no fastblur dependency
- Remove melting effect entirely (seems to be hard to implement
- properely, tried multiple itterations)
- Drop unused dependencies: fastblur, rand
- Add clap_complete dependency + --completions {bash,fish,zsh} flag,
- with CompletionShell enum in config.rs
- Fix show_* flags defaulting to true: remove default_value_t=true from
- show_media, show_battery, show_network, show_bluetooth, show_album_art,
- show_caps_lock_text — all now opt-in (matching user expectation)
- Convert peek toggle to hold: toggle_peek() → set_peek_held(held: bool),
- Press calls set_peek_held(true), new Release handler iterates all
- surfaces and calls set_peek_held(false), matching Ctrl-hold behavior
- Fix cursor rendering: increase font size 11→14 for peeked chars,
- handle cursor_position == 0 (prevent negative t wrapping to far ring
- end)
- Fix peek hit-test: use shape-aware point_in_shape() instead of simple
- circle pill/square/diamond/hexagon now detect clicks correctly within
- their area
- Remove per-frame DEBUG logs: PEEK/DOT mode in lock.rs,
- set_password_display/peek_password in render/mod.rs
- Update README: embed rustlock-effects.webp demo, remove melting
- references, correct show_* defaults and options table
