# COPR-0003 — Daily update

As a maintainer, I run one command that keeps the whole repo current without manual steps.

Chains: bump versions from upstream tags → format → full build cycle → regenerate docs → push
COPR description → commit the result as "Daily update: <date>". Intended to run unattended
(e.g. from an external nightly cron); the repo itself has no scheduler.
