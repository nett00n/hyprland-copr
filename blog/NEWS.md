# News

Maintainer's microblog, informal. Newest first, dated `## YYYY-MM-DD` entries, one short
paragraph each. README shows the most recent entries - see
`scripts/gen-report.py:get_recent_news()`.

## 2026-08-01

Big automation update. New packages: snappy switcher, mpvpaper. Switched build-state storage
instead of using yaml for storing build-related data, the sqlite is now used.
Not so simple, but yaml was really messed up and limits architechture.

## 2026-06-30

New packages: snappy switcher, mpvpaper. Added a `recommends` field to package config.

## 2026-04-24

`release` a thing now, and shows real counter of builds for current version of package. The most ofthen cause of rebuild would be the dependency version update.
Recently all packages were build as 1.2.3-1, where "1.2.3" - was a version and "1" was a static %autorelease. But this was breaking a depedency find process. I could just replace 1 in packages.yaml, but humans are making mistakes, so full-cycle autoicrement release, while building a package.
Replaced all YAML writes with ruamel lib for simplifying code and unifying

## 2026-04-08

Surely i can say, hyprland builds are pretty stable for now (yeah-yeah-yeah, ARM builds are failing, i know). Most troubles are found, new updates are working automatically without any operator activity. Minor bugs stayed, plan to fix them later, before splitting this repo in two: for automations and repo content itself.

I think i can plan a cronjob to really check for updates nightly. I started this froject 2026-02-25 so it tooks me almost two month to reach this point.

Cool, i guess

PS. Spec file now contains versions of build requirements for better debugging
## 2026-04-05

Added Waybar, cliphist, uwsm, quickshell. Refactored the main script, added log levels and
tests, more automatic error detection. Cargo vendoring is still a mess - not tackling it yet.

## 2026-03-21

Moved the build report to its own page with more detail and COPR's native build badge. Added
build-signature caching to drastically cut rebuild counts, sped up scheduled builds with
detached COPR submissions, more errors auto-highlighted now.

## 2026-03-15

Switched from toolbox to Podman/Docker for better isolation. Merged the split YAML report into
one, made it update gradually, improved the version-update submodule, made vendoring
conditional, added `SKIP_PACKAGES`.

## 2026-03-10

I have decided not to support Fedora 42 in this repository.
Compilation of Hyprland and some of it's componens needs to increase C++ compiler version.
Also Fedora would not provide security updates for this versions after May.
I don't think it worth it to spend time on this support.
I would recommend to update to Fedora 43 in this case.
