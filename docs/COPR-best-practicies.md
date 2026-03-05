Here is a **Fedora / Copr best-practice workflow** to package and publish
**Wofi** to **Copr** the *proper* way — following Fedora packaging guidelines and avoiding common mistakes.

This is the method used by experienced Fedora maintainers.

---

# 🏆 Best Practice Overview

**Do NOT:**

* ❌ Build RPMs directly in Docker and upload binaries
* ❌ Manually craft tarballs when upstream provides them
* ❌ Hardcode dependency package names

**DO:**

* ✅ Build **SRPM only**
* ✅ Use upstream release tarball
* ✅ Use `pkgconfig()` BuildRequires
* ✅ Let Copr build in clean mock chroot
* ✅ Keep packaging in Git
* ✅ Automate version bumps

---

# 🧱 1. Use Upstream Release Tarballs (Not Git Snapshots)

Best practice is:

```spec
Source0: https://github.com/SeriousBug/wofi/archive/refs/tags/v%{version}.tar.gz
```

Why?

* Reproducible
* No manual tar creation
* Copr downloads source itself
* Matches upstream checksum

---

# 📦 2. Proper SPEC File (Production Grade)

Minimal but correct example:

```spec
Name:           wofi
Version:        1.4.1
Release:        1%{?dist}
Summary:        Wayland application launcher

License:        GPL-3.0-or-later
URL:            https://github.com/SeriousBug/wofi
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  gcc
BuildRequires:  pkgconfig(gtk+-3.0)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(gdk-pixbuf-2.0)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols)

%description
Wofi is a launcher/menu program designed for Wayland compositors.

%prep
%autosetup -n %{name}-%{version}

%build
%meson
%meson_build

%install
%meson_install

%files
%license LICENSE
%doc README.md
%{_bindir}/wofi
%{_datadir}/applications/*.desktop
%{_mandir}/man1/*

%changelog
* Fri Feb 27 2026 Your Name <you@example.com> - 1.4.1-1
- Initial package
```

---

# 🔍 3. Correct Way to Define Dependencies

## BuildRequires (build-time)

Best practice:

```spec
BuildRequires: pkgconfig(gtk+-3.0)
```

NOT:

```spec
BuildRequires: gtk3-devel   ❌
```

Why?

* More portable
* Automatically resolved via pkg-config virtual provides
* Required by Fedora Packaging Guidelines

---

## How to Discover Build Dependencies

### Step 1 — Inspect Meson

```bash
meson setup build
```

Meson prints missing dependencies.

### Step 2 — Check pkg-config names

```bash
pkg-config --list-all | grep gtk
```

Then convert:

```
gtk+-3.0 → pkgconfig(gtk+-3.0)
```

---

## Runtime Requires

Usually **do not manually add them**.

RPM auto-generates them based on linked libraries.

Only add manual `Requires:` if:

* Script dependency
* External runtime tool
* Non-library requirement

---

# 🏗 4. NEVER Build Binary RPMs Locally for Copr

Best practice flow:

```bash
rpmbuild -bs wofi.spec
```

This creates:

```
wofi-1.4.1-1.fc41.src.rpm
```

Upload SRPM to Copr:

```bash
copr-cli build nett00n/wofi wofi-1.4.1-1.fc41.src.rpm
```

Why?

Copr will:

* Create clean mock chroot
* Install only BuildRequires
* Ensure reproducibility
* Catch missing dependencies

---

# 🧪 5. Test Locally Using Mock (Professional Method)

Instead of Docker:

```bash
sudo dnf install mock
```

Add yourself to mock group:

```bash
sudo usermod -aG mock $USER
```

Re-login.

Then:

```bash
mock -r fedora-41-x86_64 --rebuild wofi-*.src.rpm
```

This replicates Copr exactly.

Mock > Docker for RPM packaging.

---

# 🗂 6. Keep Packaging in Git (Critical Best Practice)

Create repo like:

```
wofi-rpm/
 ├── wofi.spec
 └── .gitignore
```

Version control your SPEC file.

Why?

* Track changes
* Easier updates
* Automate builds
* Cleaner collaboration

---

# 🚀 7. Copr Best Practice Workflow

## Create project once

```bash
copr-cli create nett00n/wofi \
    --chroot fedora-41-x86_64 \
    --description "Wofi package"
```

## Submit new builds

```bash
rpmbuild -bs wofi.spec
copr-cli build nett00n/wofi wofi-*.src.rpm
```

---

# 🔄 8. Best Practice: Updating to New Upstream Release

1. Check latest tag on GitHub
2. Update:

```spec
Version:
```

3. Reset Release:

```spec
Release: 1%{?dist}
```

4. Add changelog entry
5. Build new SRPM
6. Submit to Copr

---

# 🤖 9. Advanced Best Practice (Recommended)

## Use Copr Git Integration

Instead of uploading SRPM manually:

* Connect Copr to GitHub repo
* Push spec updates
* Copr auto-builds

This is the most professional workflow.

---

# 🧼 10. Clean Packaging Checklist

Before publishing:

* [ ] `rpmlint` passes
* [ ] No hardcoded paths
* [ ] No bundled libraries
* [ ] Uses `%meson` macros
* [ ] Uses `pkgconfig()` BuildRequires
* [ ] Builds in mock
* [ ] No unnecessary manual `Requires`

---

# 🏁 Final Professional Workflow

1. Maintain SPEC in Git
2. Use upstream tarball
3. Use pkgconfig() dependencies
4. Build SRPM only
5. Test with mock
6. Submit to Copr
7. Let Copr publish

That is Fedora-level best practice.
