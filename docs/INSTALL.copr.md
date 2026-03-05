
## Enable the repository

Regular Fedora
```shell
dnf copr enable nett00n/hyprland
```

Fedora Atomic:

```shell
FEDORA_VERSION_ID=$( grep ^VERSION_ID /etc/os-release | awk -F '=' '{print$2}')
https://copr.fedorainfracloud.org/coprs/nett00n/hyprland/repo/fedora-${FEDORA_VERSION_ID}/nett00n-hyprland-fedora-${FEDORA_VERSION_ID}.repo | sudo tee /etc/yum.repos.d/_copr:copr.fedorainfracloud.org:nett00n:hyprland.repo
```

## Install packages

```shell
dnf install hyprland
# Or
rpm-ostree install hyprland
```

Replace `hyprland` with any package from this repository. For example:

Regular Fedora:

```shell
dnf install hyprland hyprland-plugins hypridle hyprlock hyprpaper
```

Fedora Atomic:

```shell
rpm-ostree install hyprland hyprland-plugins hypridle hyprlock hyprpaper
```

## Source

Spec files and build scripts: [github.com/nett00n/hyprland-copr](https://github.com/nett00n/hyprland-copr)
