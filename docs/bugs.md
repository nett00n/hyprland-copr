# Bugs

- `make update-daily` failed because of new dependency for hyprgraphics. deps updated, `make full-cycle PKG=hyprgrafics` was ok, yet `make update-daily` set hyprgraphics to be rebuilt again #low
