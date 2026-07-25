# COPR-0008 — RPM release auto-increment

As a maintainer, I don't hand-track RPM `release` numbers.

Rule: release resets to 1 when a package's version changes, increments by 1 when its content
changes with the same version, and cascades to packages that depend on it. Any package's
release can be pinned with a manual lock to opt out of auto-increment.
