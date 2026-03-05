# Error: Go dependency download fails in mock chroot

`2026-03-05` | `spf13-cobra` | stage: mock | fc43

## Error

```
go get -v ./...
go: github.com/cpuguy83/go-md2man/v2@v2.0.6: Get "https://proxy.golang.org/...": dial tcp: lookup proxy.golang.org on [::1]:53: read udp [...]: read: connection refused
make: *** [Makefile:32: install_deps] Error 1
error: Bad exit status from /var/tmp/rpm-tmp.nuWm1U (%build)
```

## Meaning

Mock chroots have no network access. Any `go get`, `go mod download`, or `go install`
call during `%build` will fail because the Go module proxy is unreachable.

COPR cloud builds have the same constraint — the build worker is also network-isolated.
However, COPR builds from a submitted **SRPM**, which is a self-contained archive.
If the vendor tarball is included as a source file when `rpmbuild -bs` runs locally,
it gets embedded into the SRPM and is available to the COPR worker without any network
access.

## Fix

### Automated (full-cycle)

`stage-vendor.py` runs automatically between `stage-spec` and `stage-srpm` in
`full-cycle.py`. It detects Go packages (those with `golang` in `build_requires`),
generates `<name>-<version>-vendor.tar.gz` in `~/rpmbuild/SOURCES/`, and skips
packages whose tarball already exists.

`stage-srpm.py` then runs `rpmbuild -bs`, which embeds the vendor tarball into the
SRPM. `stage-copr.py` uploads the SRPM — the COPR worker extracts it and builds
entirely offline.

### Manual (one package)

```bash
python3 scripts/gen-vendor-tarball.py <package-name>
# writes ~/rpmbuild/SOURCES/<name>-<version>-vendor.tar.gz
```

### Spec changes required

1. Add `Source1` referencing the vendor tarball by filename (not URL):
   ```
   Source1: %{name}-%{version}-vendor.tar.gz
   ```

2. Extract it in `%prep` after the main source:
   ```
   %autosetup -n <source-name>-%{version}
   tar xf %{SOURCE1}
   ```

3. Use `-mod=vendor` in `%build` (or the `%gobuild` macro from `go-rpm-macros`):
   ```
   BuildRequires: go-rpm-macros
   ...
   %gobuild -o %{_builddir}/%{name} ./...
   ```
   `%gobuild` automatically passes `-mod=vendor` when a `vendor/` directory is present.

## Notes

- The vendor tarball unpacks as a bare `vendor/` directory (no wrapper dir),
  so `tar xf %{SOURCE1}` inside the already-extracted source tree works directly.
- Re-generate (or delete from `~/rpmbuild/SOURCES/`) whenever the upstream version
  or `go.mod` changes. `stage-vendor.py` skips existing tarballs, so deletion is
  the trigger for regeneration.
- For packages where upstream already ships a `vendor/` in the release tarball,
  skip vendoring entirely and just build with `-mod=vendor`.
