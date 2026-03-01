# Error: list-submodule-tags add generates wrong sources.url

`2026-03-01` | `scripts/list-submodule-tags.py` | stage: spec | fc43

## Error

```
    sources:
      - url: "%https://github.com/hyprwm/hyprcursor/archive/refs/tags/v%0.1.13.tar.gz"
```

## Meaning

In `cmd_add()`, the source URL template was built with an f-string:

```python
f'      - url: "%{url}/archive/refs/tags/v%{version}.tar.gz"\n',
```

Python f-strings evaluate `{url}` and `{version}` as format placeholders, substituting
the local variables instead of emitting the RPM macros `%{url}` and `%{version}`.

## Fix

Escape the curly braces in the f-string so they pass through as literals:

```python
f'      - url: "%{{url}}/archive/refs/tags/v%{{version}}.tar.gz"\n',
```

`{{` → `{` and `}}` → `}` in Python f-strings, producing the correct RPM macro syntax.

## Notes

Any f-string that needs to emit a literal `{...}` (e.g. RPM macros, shell variables,
Jinja2 expressions) must double the braces. Easy to miss when the variable names happen
to match local Python variables (`url`, `version` both exist in scope).
