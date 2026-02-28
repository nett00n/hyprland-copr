# Error: hyprpaper dnf5 builddep fails — local-repo / Fedora ABI conflict

`2026-02-28` | `hyprpaper` | stage: mock | fc43

## Error

```
Failed to resolve the transaction:
Problem: cannot install both hyprutils-0.7.1-4.fc43.x86_64 from fedora
                          and hyprutils-0.11.0-1.fc43.fc43.x86_64 from local-repo
  - package hyprgraphics-0.1.5-2.fc43.x86_64 from fedora requires libhyprutils.so.6()(64bit),
    but none of the providers can be installed
```

## Meaning

Partial chain build left `local-repo` inconsistent: `hyprutils 0.11.0` was built and added, but `hyprgraphics 0.5.0` failed and was not. When resolving `hyprpaper`'s deps, DNF5 finds `hyprgraphics-devel` only from Fedora (0.1.5, built against old `libhyprutils.so.6`) while `hyprutils-devel` comes from local-repo (0.11.0, different soname). No consistent package set exists.

## Fix

1. Fix `hyprgraphics` first — see `2026-02-28-hyprgraphics-missing-deps-v0.5.0.md`. Once it builds successfully and lands in `local-repo`, `hyprpaper`'s builddep resolves cleanly.
2. Guard `full-cycle.py` against continuing downstream when an upstream build failed — skip packages whose local-dep prerequisites are not yet in `local-repo`.

## Notes

- `local-repo` must be a consistent superset of what it overrides. A partial upgrade (newer `hyprutils` without a matching `hyprgraphics`) makes downstream unresolvable.
- When any package in the chain fails, abort dependents rather than attempting them and getting confusing conflict errors.
