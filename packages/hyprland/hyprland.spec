Name:           hyprland
Version:        0.54.1
Release:        %autorelease%{?dist}
Summary:        A Modern C++ Wayland Compositor
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/Hyprland
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  hyprutils-devel
BuildRequires:  hyprwayland-scanner-devel
BuildRequires:  hyprwire-devel
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(aquamarine)
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(gl)
BuildRequires:  pkgconfig(glesv2)
BuildRequires:  pkgconfig(hyprcursor)
BuildRequires:  pkgconfig(hyprgraphics)
BuildRequires:  pkgconfig(hyprland-protocols)
BuildRequires:  pkgconfig(hyprlang)
BuildRequires:  pkgconfig(hyprutils)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libinput)
BuildRequires:  pkgconfig(muparser)
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(pangocairo)
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(re2)
BuildRequires:  pkgconfig(tomlplusplus)
BuildRequires:  pkgconfig(uuid)
BuildRequires:  pkgconfig(wayland-protocols)
BuildRequires:  pkgconfig(wayland-server)
BuildRequires:  pkgconfig(xcb-errors)
BuildRequires:  pkgconfig(xcb-icccm)
BuildRequires:  pkgconfig(xcursor)
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  udis86-devel
BuildRequires:  glaze-devel

%description
Hyprland is a 100% independent, dynamic tiling Wayland compositor that doesn't sacrifice on its looks.

It provides the latest Wayland features, is highly customizable, has all the eyecandy, the most powerful plugins, easy IPC, much more QoL stuff than other compositors and more...

%prep
%autosetup -n Hyprland-%{version}
sed -i 's|^install(TARGETS start-hyprland)|target_include_directories(start-hyprland PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/../glaze-src/include")\ninstall(TARGETS start-hyprland)|' start/CMakeLists.txt

%build
%cmake
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_bindir}/hyprctl
%{_bindir}/hyprland
%{_prefix}/bin/Hyprland
%{_bindir}/hyprpm
%{_bindir}/start-hyprland
%{_datadir}/bash-completion/completions/hyprctl
%{_datadir}/bash-completion/completions/hyprpm
%{_datadir}/fish/vendor_completions.d/hyprctl.fish
%{_datadir}/fish/vendor_completions.d/hyprpm.fish
%{_datadir}/hypr/
%{_datadir}/wayland-sessions/hyprland*.desktop
%{_datadir}/xdg-desktop-portal/hyprland-portals.conf
%{_datadir}/zsh/site-functions/_hyprctl
%{_datadir}/zsh/site-functions/_hyprpm
%{_mandir}/man1/hyprctl.1.gz
%{_mandir}/man1/Hyprland.1.gz

%package devel
Summary:        Development files for A Modern C++ Wayland Compositor
Requires:       %{name} = %{version}-%{release}

%description devel
Development files for hyprland.

%files devel
%{_includedir}/hyprland/
%{_prefix}/share/pkgconfig/hyprland.pc

%changelog
* Tue Mar 03 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.54.1-%autorelease
- This is a standard patch release backporting some fixes from main onto 0.54.0
- algo/dwindle: add back splitratio (#13498)
- hyprpm: fix url sanitization in add
- algo/master: fix crash after dpms (#13522)
- algo/scrolling: fix offset on removeTarget (#13515)
- algo/scrolling: fix rare crash
- build: fix build on gcc 16.x after #6b2c08d (#13429)
- compositor: fix focus edge detection (#13425)
- deco/border: fix damageEntire
- desktop/group: fix movegroupwindow not following focus (#13426)
- desktop/rule: fix matching for content type by str
- desktop/window: fix floating windows being auto-grouped (#13475)
- desktop/window: fix idealBB reserved (#13421)
- hyprctl: fix buffer overflowing writes to the socket
- hyprctl: fix workspace dynamic effect reloading (#13537)
- hyprpm: fix url sanitization in add
- keybinds: fixup changegroupactive
- layout/algo: fix swar on removing a target (#13427)
- layout/scroll: fix configuredWidths not setting properly on new workspaces (#13476)
- layout/scrolling: fix size_t underflow in idxForHeight (#13465)
- layout/windowTarget: fix size_limits_tiled (#13445)
- layouts: fix crash on missed relayout updates (#13444)
- renderer: fix crash on mirrored outputs needing recalc (#13534)
- screencopy: fix nullptr deref if shm format is weird
- tests/workspace: fix one test case failing
- algo/dwindle: don't crash on empty swapsplit (#13533)
- algo/dwindle: use focal point correctly for x-ws moves (#13514)
- algo/scroll: improve directional moves (#13423)
- build: remove auto-generated hyprctl/hw-protocols/ files during make clear (#13399)
- compositor: damage monitors on workspace attachment updates
- desktop/group: respect direction when moving window out of group (#13490)
- desktop/window: don't group modals
- format: safeguard drmGetFormat functions (#13416)
- layout/algos: use binds:window_direction_monitor_fallback for moves (#13508)
- layout/windowTarget: damage before and after moves (#13496)
- layout/windowTarget: don't use swar on maximized (#13501)
- layout/windowTarget: override maximized box status in updateGeom (#13535)
- layout: store and preserve size and pos after fullscreen (#13500)
- monitor: damage old special monitor on change
- monitor: keep workspace monitor bindings on full reconnect (#13384)
- monitor: update pinned window states properly on changeWorkspace (#13441)
- pointer: damage entire buffer in begin of rendering hw
- screencopy: scale window region for toplevel export (#13442)
- scroll: clamp column widths properly
- As always, massive thanks to our wonderful donators and sponsors:
- 37Signals
- Framework
- Seishin, Kay, johndoe42, d, vmfunc, Theory_Lukas, --, MasterHowToLearn, iain, ari-cake, TyrHeimdal, alexmanman5, MadCatX, Xoores, inittux111, RaymondLC92, Insprill, John Shelburne, Illyan, Jas Singh, Joshua Weaver, miget.com, Tonao Paneguini, Brandon Wang, Arkevius, Semtex, Snorezor, ExBhal, alukortti, lzieniew, taigrr, 3RM, DHH, Hunter Wesson, Sierra Layla Vithica, soy_3l.beantser, Anon2033, Tom94
- monkeypost, lorenzhawkes, Adam Saudagar, Donovan Young, SpoderMouse, prafesa, b3st1m0s, CaptainShwah, Mozart409, bernd, dingo, Marc Galbraith, Mongoss, .tweep, x-wilk, Yngviwarr, moonshiner113, Dani Moreira, Nathan LeSueur, Chimal, edgarsilva, NachoAz, mo, McRealz, wrkshpstudio, crutonjohn
- macsek, kxwm, Bex Jonathan, Alex, Tomas Kirkegaard, Viacheslav Demushkin, Clive, phil, luxxa, peterjs, tetamusha, pallavk, michaelsx, LichHunter, fratervital, Marpin, SxK, mglvsky, Pembo, Priyav Shah, ChazBeaver, Kim, JonGoogle, matt p, tim, ybaroj, Mr. Monet Baches, NoX, knurreleif, bosnaufal, Alex Vera, fathulk, nh3, Peter, Charles Silva, Tyvren, BI0L0G0S, fonte-della-bonitate, Alex Paterson, Ar, sK0pe, criss, Dnehring, Justin, hylk, 邱國玉KoryChiu, KSzykula, Loutci, jgarzadi, vladzapp, TonyDuan, Brian Starke, Jacobrale, Arvet, Jim C, frank2108, Bat-fox, M.Bergsprekken, sh-r0, Emmerich, davzucky, 3speed, 7KiLL, nu11p7r, Douglas Thomas, Ross, Dave Dashefsky, gignom, Androlax, Dakota, soup, Mac, Quiaro, bittersweet, earthian, Benedict Sonntag, Plockn, Palmen, SD, CyanideData, Spencer Flagg, davide, ashirsc, ddubs, dahol, C. Willard A.K.A Skubaaa, ddollar, Kelvin, Gwynspring, Richard, Zoltán, FirstKix, Zeux, CodeTex, shoedler, brk, Ben Damman, Nils Melchert, Ekoban, D., istoleyurballs , gaKz, ComputerPone, Cell the Führer, defaltastra, Vex, Bulletcharm, cosmincartas, Eccomi, vsa, YvesCB, mmsaf, JonathanHart, Sean Hogge, leat bear, Arizon, JohannesChristel, Darmock, Olivier, Mehran, Anon, Trevvvvvvvvvvvvvvvvvvvv, C8H10N4O2, BeNe, Ko-fi Supporter :3, brad, rzsombor, Faustian, Jemmer, Antonio Sanguigni, woozee, Bluudek, chonaldo, LP, Spanching, Armin, BarbaPeru, Rockey, soba, FalconOne, eizengan, むらびと, zanneth, 0xk1f0, Luccz, Shailesh Kanojia, ForgeWork , Richard Nunez, keith groupdigital.com, pinklizzy, win_cat_define, Bill, johhnry, Matysek, anonymus, github.com/wh1le, Iiro Ullin, Filinto Delgado, badoken, Simon Brundin, Ethan, Theo Puranen Åhfeldt, PoorProgrammer, lukas0008, Paweł S, Vandroiy, Mathias Brännström, Happyelkk, zerocool823, Bryan, ralph_wiggums, DNA, skatos24, Darogirn , Hidde, phlay, lindolo25, Siege, Gus, Max, John Chukwuma, Loopy, Ben, PJ, mick, herakles, mikeU-1F45F, Ammanas, SeanGriffin, Artsiom, Erick, Marko, Ricky, Vincent mouline
- **Full Changelog**: https://github.com/hyprwm/Hyprland/compare/v0.54.0...v0.54.1
