# Error: unknown PACKAGE= crashes with ValueError in print_summary

`2026-03-01` | `scripts/full-cycle.py` | stage: copr | fc43

## Error

```
  File "/var/home/nett00n/personal-env/hyprland-copr/scripts/full-cycle.py", line 127, in print_summary
    col_w = max(len(p) for p in packages) + 2
            ~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: max() iterable argument is empty
```

## Meaning

When `PACKAGE=<name>` is set to a package not present in `packages.yaml`, the filter:

```python
packages = {n: all_packages[n] for n in names if n in all_packages}
```

silently drops the unknown name, leaving `packages` as an empty dict.
`print_summary()` then calls `max()` on an empty iterable and crashes.

## Fix

Validate unknown names before filtering and exit with a clear error:

```python
unknown = [n for n in names if n not in all_packages]
if unknown:
    sys.exit(f"error: unknown package(s): {', '.join(unknown)}")
packages = {n: all_packages[n] for n in names}
```

## Notes

The crash happens at the very end of `main()` (after all build stages complete),
so all stage output is already gone by the time the traceback appears — making it
look like the build ran silently with no results.
