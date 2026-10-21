# COPR-0026. Gotify notifications

**Tags:** #daily #notifications #tooling

## User Story

As a maintainer, I want a push notification when the nightly run finishes (what moved,
what was attempted, what failed), and a one-liner to send an ad-hoc event from any
script or shell, so that I learn about a broken night without opening the logs.

## Behavior

`make notify TITLE=<t> MESSAGE=<m> [PRIORITY=<n>]` sends one message to a
[Gotify](https://gotify.net) server (`POST <GOTIFY_URL>/message`, token in the
`X-Gotify-Key` header, never in the URL so it stays out of access logs). `PRIORITY`
defaults to `5`.

`make notify-summary` builds tonight's nightly summary and sends it with the title
`hyprland-copr update-daily`. `_update-daily` runs it as its last step, **before** the
build-failure exit, so a failed night is reported too:

```text
updated 3: foo 1.1.1>1.1.2, baz 2.0>2.1, qux 0.3>0.4. planned: 3, succeeded: 2, errors: bar
```

- `updated N: <pkg> <old>><new>, ...` — packages whose version `update-versions`
  changed tonight (`updated 0` with no list when none). Read from
  `logs/.update-versions-changes.json`, written by `scripts/update-versions.py`.
- `planned` — distinct packages with any `stage_history` row in a run started since
  `_update-daily` began (marker `logs/.update-daily-started`, epoch seconds).
- `succeeded` — planned packages with no `failed` stage in those runs.
- `errors` — comma-separated packages with a `failed` stage in those runs, or `none`.

Priority is `8` when `errors` is non-empty, else `5`.

`make full-cycle` and `make full-cycle-matrix` each send one message when they finish,
titled `hyprland-copr full-cycle` / `hyprland-copr full-cycle-matrix`, e.g.
`full-cycle succeeded (fedora 44 package: neowall)` or
`full-cycle-matrix FAILED exit 2 (chroots: 44 43 45 package: all)`; priority `5` on
success, `8` on failure. Runs nested inside another notifying target stay silent: the
per-chroot `full-cycle` calls of `full-cycle-matrix` and the `full-cycle-matrix` call of
`update-daily` (which sends its own summary) pass `NOTIFY=0`; pass `NOTIFY=0` by hand to
silence a direct run. Runs refused by the pipeline lock send nothing.

Configuration, from `.env` or the environment: `GOTIFY_URL` (server base URL) and
`GOTIFY_TOKEN` (application token). If either is unset the send is skipped with a
warning.

A notification failure (server down, bad token, timeout) is a warning only: both
targets exit 0, and the send has a 10 s timeout, so Gotify can never fail or stall
`update-daily`.

## Implementation

- `scripts/gotify-notify.py`: `send()`, `build_summary()`, `format_summary()`, CLI
  (`--title`, `--message`, `--priority`, `--summary`).
- `scripts/update-versions.py`: writes `logs/.update-versions-changes.json` on every
  exit path (`{}` when nothing changed).
- `Makefile`: `notify`, `notify-summary`; `_update-daily` writes the start marker and
  calls `notify-summary`; the `notify_result` macro runs `notify` from the `full-cycle`
  and `full-cycle-matrix` wrappers after the pipeline exits, unless `NOTIFY=0`.
- `.env.example`: `GOTIFY_URL`, `GOTIFY_TOKEN`.

## Quirks & Decisions

- Runs on the host `.venv` (stdlib `urllib` only), not in the container: it needs the
  network and reads `build-report.db` read-only.
- "Planned" counts packages touched in tonight's runs rather than the configured package
  set, so a `PACKAGE=`-filtered run reports what it actually attempted.
- A stale `changes.json` from a previous night is never read as tonight's: the file is
  rewritten (or emptied) by every `update-versions` run, which `_update-daily` always
  runs first.

## Testing

- Unit (`tests/test_gotify_notify.py`): `format_summary()` output for updates/none and
  errors/none; `build_summary()` windowing against a temp `build-report.db`; `send()`
  request shape (URL, `X-Gotify-Key` header, JSON body) and swallow-and-warn on
  `URLError`; missing URL/token skips without a request.
- Unit (`tests/test_update_versions.py`): the changes sentinel is written, and emptied on
  a no-op run.
- Integration (`tests/integration/test_make_targets.py`): `_update-daily` calls
  `notify-summary` ahead of the failure exit; `full-cycle` and `full-cycle-matrix` call
  `notify` after the pipeline and keep its exit status; nested calls (matrix chroots,
  `update-daily`) pass `NOTIFY=0`.

## Status

Implemented
