## Enable the repository

**Regular Fedora**:

```shell
dnf copr enable nett00n/hyprland
```

**Fedora Atomic**:

```shell
DISTRO_NAME=fedora
DISTRO_VERSION_ID=$(source /etc/os-release && echo $VERSION_ID)
COPR_USER_NAME=nett00n
COPR_REPO_NAME=hyprland

curl -sL "https://copr.fedorainfracloud.org/coprs/${COPR_USER_NAME}/${COPR_REPO_NAME}/repo/${DISTRO_NAME}-${DISTRO_VERSION_ID}/${COPR_USER_NAME}-${COPR_REPO_NAME}-${DISTRO_NAME}-${DISTRO_VERSION_ID}.repo" \
  | sudo tee /etc/yum.repos.d/_copr:copr.fedorainfracloud.org:${COPR_USER_NAME}:${COPR_REPO_NAME}.repo
```

## Install packages

```shell
dnf install hyprland
# Or
rpm-ostree install hyprland
```

Replace `hyprland` with any package from this repository. For example:

**Regular Fedora**:

```shell
dnf install hypridle hyprland hyprland-guiutils hyprlock hyprpaper hyprpwcenter hyprshutdown
```

**Fedora Atomic**:

```shell
rpm-ostree install hypridle hyprland hyprland-guiutils hyprlock hyprpaper hyprpwcenter hyprshutdown
```

## Source

Spec files and build scripts: [github.com/nett00n/hyprland-copr](https://github.com/nett00n/hyprland-copr)
