# Bugs

- `make update-daily` failed because of new dependency for hyprgraphics. deps updated, `make full-cycle PKG=hyprgrafics` was ok, yet `make update-daily` set hyprgraphics to be rebuilt again #low
- `make readme` triggers checking copr builds for each of readme files
