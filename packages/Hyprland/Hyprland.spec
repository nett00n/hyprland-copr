Name:           Hyprland
Version:        0.54.0
Release:        %autorelease%{?dist}
Summary:        A Modern C++ Wayland Compositor
License:        BSD-3-Clause
URL:            https://github.com/hyprwm/Hyprland
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz
%global glaze_version 7.0.0
Source1:        https://github.com/stephenberry/glaze/archive/refs/tags/v7.0.0.tar.gz#/glaze-7.0.0.tar.gz

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

%description
Hyprland is a 100% independent, dynamic tiling Wayland compositor that doesn't sacrifice on its looks.

It provides the latest Wayland features, is highly customizable, has all the eyecandy, the most powerful plugins, easy IPC, much more QoL stuff than other compositors and more...

%prep
%autosetup
tar xf %{SOURCE1}
mv glaze-7.0.0 glaze-src
sed -i 's|^install(TARGETS start-hyprland)|target_include_directories(start-hyprland PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/../glaze-src/include")\ninstall(TARGETS start-hyprland)|' start/CMakeLists.txt

%build
%cmake \
    -DFETCHCONTENT_FULLY_DISCONNECTED=ON \
    -DFETCHCONTENT_SOURCE_DIR_GLAZE=%{_builddir}/%{name}-%{version}/glaze-src
%cmake_build

%install
%cmake_install

%files
%doc README.md
%license LICENSE
%{_bindir}/hyprctl
%{_bindir}/hyprland
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
Development files for Hyprland.

%files devel
%{_includedir}/hyprland/
%{_pkgconfigdatadir}/hyprland.pc

%changelog
* Fri Feb 27 2026 Vladimir nett00n Budylnikov <git@nett00n.org> - 0.54.0-%autorelease
- A big (large), actually huge update for y'all!!
- Special thanks to our HIs (Human Intelligences) for powering Hyprland development.
- `togglesplit` and `swapsplit` have been removed after being long deprecated. Use `layoutmsg` with the same params instead.
- `single_window_aspect_ratio` and `single_window_aspect_ratio_tolerance` have been migrated from dwindle to layout, and are layout-agnostic
- cmakelists: add fno-omit-frame-pointer for tracy builds
- desktop/window: add stable id and use it for foreign
- gestures: add cursor zoom (#13033)
- groupbar: added group:groupbar:text_padding (#12818)
- hyprctl: add error messages to hyprctl hyprpaper wallpaper (#13234)
- hyprctl: add overFullscreen field in hyprctl window debug (#13066)
- hyprpm: add full nix integration (#13189)
- keybinds: add inhibiting gestures under shortcut inhibitors (#12692)
- main: add watchdog-fd and safe-mode options to help message (#12922)
- opengl: add debug:gl_debugging (#13183)
- start: add --force-nixgl and check /run/opengl-driver (#13385)
- start: add parent-death handling for BSDs (#12863)
- algo/dwindle: fix focal point not being properly used in movedTarget (#13373)
- algo/master: fix master:orientation being a noop
- algo/master: fix orientation cycling (#13372)
- algo/scrolling: fix crashes on destroying ws
- core/compositor: immediately do readable if adding waiter fails for scheduling state
- compositor: fix calculating x11 work area (#13347)
- config/descriptions: fix use_cpu_buffer (#13285)
- core/xwaylandmgr: fix min/max clamp potentially crashing
- decorations/border: fix damage scheduling after #12665
- desktop/layerRuleApplicator: fix an epic c+p fail
- desktop/ls: fix invalid clamp
- desktop/popup: fix use after free in Popup (#13335)
- desktop/reserved: fix a possible reserved crash (#13207)
- desktop/ruleApplicator: fix typo in border color rule parsing (#12995)
- desktop/rules: fix border colors not resetting. (#13382)
- desktop/workspaceHistory: fix tracking for multiple monitors (#12979)
- desktopAnimationMgr: fix slide direction
- dynamicPermManager: fix c+p fail
- eventLoop: various eventloopmgr fixes (#13091)
- example: fixup config for togglesplit
- fifo: miscellaneous fifo fixes (#13136)
- fix: handle fullscreen windows on special workspaces (#12851)
- hyprctl: fix layerrules not being applied dynamically with hyprctl (#13080)
- hyprerror: add padding & adjust for scale when reserving area (#13158)
- hyprerror: fix horizontal overflow and damage box (#12719)
- hyprpm: fix build step execution
- hyprpm: fix clang-format
- input: fix edge grab resize logic for gaps_out > 0 (#13144)
- input: fix kinetic scroll (#13233)
- keybinds: fix unguarded member access in moveWindowOrGroup (#13337)
- mainLoopExecutor: fix incorrect pipe check
- monitor: fix DS deactivation (#13188)
- multigpu: fix multi gpu checking (#13277)
- nix: add hyprland-uwsm to passthru.providedSessions
- nix: fix evaluation warnings, the xorg package set has been deprecated (#13231)
- pluginsystem: fix crash when unloading plugin hyprctl commands (#12821)
- protocols/cm: Fix image description info events (#12781)
- protocols/contentType: fix missing destroy
- protocols/contentType: fix typo in already constructed check
- protocols/dmabuf: fix DMA-BUF checks and events (#12965)
- protocols/syncobj: fix DRM sync obj support logging (#12946)
- renderer/pass: fix surface opaque region bounds used in occluding (#13124)
- renderer: add surface shader variants with less branching and uniforms (#13030)
- renderer: optimise shader usage further, split shaders and add more caching (#12992)
- renderer: fix dgpu directscanout explicit sync (#13229)
- renderer: fix frame sync (#13061)
- renderer: fix mouse motion in VRR (#12665)
- renderer: fix non shader cm reset (#13027)
- renderer: fix screen export back to srgb (#13148)
- systemd/sdDaemon: fix incorrect strnlen
- target: fix geometry for x11 floats
- tester: fix sleeps waiting for too long (#12774)
- xwayland/xwm: fix _NET_WM_STATE_MAXIMIZED_VERT type (#13151)
- xwayland/xwm: fix window closing when props race
- xwayland: fix size mismatch for no scaling (#13263)
- Nix: apply glaze patch
- Nix: re-enable hyprpm
- Reapply "hyprpm: bump glaze version"
- Revert "hyprpm: bump glaze version"
- algo/scrolling: adjust focus callbacks to be more intuitive
- animation: reset tick state on session activation (#13024)
- animationMgr: avoid uaf in ::tick() if handleUpdate destroys AV
- anr: open anr dialog on parent's workspace (#12509)
- anr: remove window on closewindow (#13007)
- buffer: add move constructor and operator to CHLBufferReference (#13157)
- cm: block DS for scRGB in HDR mode (#13262)
- cmake: bump wayland-server version to 1.22.91 (#13242)
- cmake: use OpenGL::GLES3 when OpenGL::GL does not exist (#13260)
- cmakelists: don't require debug for tracy
- compositor: guard null view() in getWindowFromSurface (#13255)
- config: don't crash on permission with a config check
- config: return windowrulev2 layerrulev2 error messages (#12847)
- config: support no_vrr rule on vrr 1 (#13250)
- core: optimize some common branches
- decoration: take desiredExtents on all sides into account (#12935)
- dekstop/window: read static rules before guessing initial size if possible (#12783)
- desktop/LS: avoid creating an invalid LS if no monitor could be found (#12787)
- desktop/ls: clamp layer from protocol
- desktop/popup: avoid crash on null popup child in rechecking
- desktop/popup: only remove reserved for window popups
- desktop/reservedArea: clamp dynamic types to 0
- desktop/reservedArea: clamp to 0
- desktop/rules: use pid for exec rules (#13374)
- desktop/window: avoid uaf on instant removal of a window
- desktop/window: catch bad any cast tokens
- desktop/window: go back to the previously focused window in a group (#12763)
- desktop/window: remove old fn defs
- desktop/window: track explicit workspace assignments to prevent X11 configure overwrites (#12850)
- desktop/window: use workArea for idealBB (#12802)
- desktop/windowRule: allow expression in min_size/max_size (#12977)
- desktop/windowRule: use content rule as enum directly (#13275)
- desktop: restore invisible floating window alpha/opacity when focused over fullscreen (#12994)
- event: refactor HookSystem into a typed event bus (#13333)
- eventLoop: remove failed readable waiters
- framebuffer: revert viewport (#12842)
- gestures/fs: remove unneeded floating state switch (#13127)
- hyprctl: adjust json case
- hyprctl: bump hyprpaper protocol to rev 2 (#12838)
- hyprctl: remove trailing comma from json object (#13042)
- hyprerror: clear reserved area on destroy (#13046)
- hyprpm,Makefile: drop cmake ninja build
- hyprpm: bump glaze version
- hyprpm: drop meson dep
- hyprpm: exclude glaze from all targets during fetch
- hyprpm: use provided pkgconf env if available
- i18n: add Romanian translations (#13075)
- i18n: add Traditional Chinese (zh_TW) translations (#13210)
- i18n: add Vietnamese translation (#13163)
- i18n: add bengali translations (#13185)
- i18n: update russian translation (#13247)
- input/TI: avoid UAF in destroy
- input/ti: avoid sending events to inactive TIs
- input: guard null `view()` when processing mouse down (#12772)
- input: use fresh cursor pos when sending motion events (#13366)
- internal: removed Herobrine
- layershell: restore focus to layer shell surface after popup is destroyed (#13225)
- layout: rethonk layouts from the ground up (#12890)
- monitor: revert "remove disconnected monitor before unsafe state #12544" (#13154)
- nix: remove glaze patch
- opengl/fb: use GL_DEPTH24_STENCIL8 instead of GL_STENCIL_INDEX8 (#13067)
- opengl: allow texture filter to be changed (#13078)
- opengl: set EGL_CONTEXT_RELEASE_BEHAVIOR_KHR if supported (#13114)
- pointermgr: damage only the surface size (#13284)
- pointermgr: remove onRenderBufferDestroy (#13008)
- pointermgr: revert "damage only the surface size (#13284)"
- popup: check for expired weak ptr (#13352)
- popup: reposition with reserved taken into account
- proto/shm: update wl_shm to v2 (#13187)
- protocolMgr: remove IME / virtual input protocols from sandbox whitelist
- protocols/toplevelExport: Support transparency in toplevel export (#12824)
- protocols: implement image-capture-source-v1 and image-copy-capture-v1 (#11709)
- renderer/fb: dont forget to set m_drmFormat (#12833)
- renderer/gl: add internal gl formats and reduce internal driver format conversions (#12879)
- renderer/opengl: invalidate intermediate FBs post render, avoid stencil if possible (#12848)
- renderer: allow tearing with DS with invisible cursors (#13155)
- renderer: better sdr eotf settings (#12812)
- renderer: minor framebuffer and renderbuffer changes (#12831)
- renderer: shader code refactor (#12926)
- shm: ensure we use right gl unpack alignment (#12975)
- start: use nixGL if Hyprland is nix but not NixOS (#12845)
- systemd/sdDaemon: initialize sockaddr_un
- testers: add missing #include <unistd.h> (#12862)
- tests: Test the `no_focus_on_activate` window rule (#13015)
- time: ensure type correctness and calculate nsec correctly (#13167)
- versionKeeper: ignore minor rev version
- view: send wl_surface.enter to subsurfaces of popups (#13353)
- wayland/output: return all bound wl_output instances in outputResourceFrom (#13315)
- welcome: skip in safe mode
- xwayland/xwm: get supported props on constructing surface (#13156)
- xwayland/xwm: handle INCR clipboard transfer chunks correctly (#13125)
- xwayland/xwm: prevent onWrite infinite loop and clean orphan transfers (#13122)
- xwayland: ensure NO_XWAYLAND builds (#13160)
- xwayland: normalize OR geometry to logical coords with force_zero_scaling (#13359)
- xwayland: validate size hints before floating (#13361)
- As always, massive thanks to our wonderful donators and sponsors:
- 37Signals
- Framework
- Seishin, Kay, johndoe42, d, vmfunc, Theory_Lukas, --, MasterHowToLearn, iain, ari-cake, TyrHeimdal, alexmanman5, MadCatX, Xoores, inittux111, RaymondLC92, Insprill, John Shelburne, Illyan, Jas Singh, Joshua Weaver, miget.com, Tonao Paneguini, Brandon Wang, Arkevius, Semtex, Snorezor, ExBhal, alukortti, lzieniew, taigrr, 3RM, DHH, Hunter Wesson, Sierra Layla Vithica, soy_3l.beantser, Anon2033, Tom94
- monkeypost, lorenzhawkes, Adam Saudagar, Donovan Young, SpoderMouse, prafesa, b3st1m0s, CaptainShwah, Mozart409, bernd, dingo, Marc Galbraith, Mongoss, .tweep, x-wilk, Yngviwarr, moonshiner113, Dani Moreira, Nathan LeSueur, Chimal, edgarsilva, NachoAz, mo, McRealz, wrkshpstudio, crutonjohn
- macsek, kxwm, Bex Jonathan, Alex, Tomas Kirkegaard, Viacheslav Demushkin, Clive, phil, luxxa, peterjs, tetamusha, pallavk, michaelsx, LichHunter, fratervital, Marpin, SxK, mglvsky, Pembo, Priyav Shah, ChazBeaver, Kim, JonGoogle, matt p, tim, ybaroj, Mr. Monet Baches, NoX, knurreleif, bosnaufal, Alex Vera, fathulk, nh3, Peter, Charles Silva, Tyvren, BI0L0G0S, fonte-della-bonitate, Alex Paterson, Ar, sK0pe, criss, Dnehring, Justin, hylk, 邱國玉KoryChiu, KSzykula, Loutci, jgarzadi, vladzapp, TonyDuan, Brian Starke, Jacobrale, Arvet, Jim C, frank2108, Bat-fox, M.Bergsprekken, sh-r0, Emmerich, davzucky, 3speed, 7KiLL, nu11p7r, Douglas Thomas, Ross, Dave Dashefsky, gignom, Androlax, Dakota, soup, Mac, Quiaro, bittersweet, earthian, Benedict Sonntag, Plockn, Palmen, SD, CyanideData, Spencer Flagg, davide, ashirsc, ddubs, dahol, C. Willard A.K.A Skubaaa, ddollar, Kelvin, Gwynspring, Richard, Zoltán, FirstKix, Zeux, CodeTex, shoedler, brk, Ben Damman, Nils Melchert, Ekoban, D., istoleyurballs , gaKz, ComputerPone, Cell the Führer, defaltastra, Vex, Bulletcharm, cosmincartas, Eccomi, vsa, YvesCB, mmsaf, JonathanHart, Sean Hogge, leat bear, Arizon, JohannesChristel, Darmock, Olivier, Mehran, Anon, Trevvvvvvvvvvvvvvvvvvvv, C8H10N4O2, BeNe, Ko-fi Supporter :3, brad, rzsombor, Faustian, Jemmer, Antonio Sanguigni, woozee, Bluudek, chonaldo, LP, Spanching, Armin, BarbaPeru, Rockey, soba, FalconOne, eizengan, むらびと, zanneth, 0xk1f0, Luccz, Shailesh Kanojia, ForgeWork , Richard Nunez, keith@groupdigital.com, pinklizzy, win_cat_define, Bill, johhnry, Matysek, anonymus, github.com/wh1le, Iiro Ullin, Filinto Delgado, badoken, Simon Brundin, Ethan, Theo Puranen Åhfeldt, PoorProgrammer, lukas0008, Paweł S, Vandroiy, Mathias Brännström, Happyelkk, zerocool823, Bryan, ralph_wiggums, DNA, skatos24, Darogirn , Hidde, phlay, lindolo25, Siege, Gus, Max, John Chukwuma, Loopy, Ben, PJ, mick, herakles, mikeU-1F45F, Ammanas, SeanGriffin, Artsiom, Erick, Marko, Ricky, Vincent mouline
- **Full Changelog**: https://github.com/hyprwm/Hyprland/compare/v0.53.0...v0.54.0
