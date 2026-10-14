#!/bin/sh
# Fixed, privileged dependency setup. No downloaded script is executed as root.
set -eu
task_user=${1:?Missing launching user}
task_mode=${2:-vm}
case "$task_mode" in vm|native) ;; *) exit 2 ;; esac
[ "$(id -u)" = 0 ] || { printf '%s\n' 'Setup needs administrator permission.' >&2; exit 1; }
getent passwd "$task_user" >/dev/null
if command -v apt-get >/dev/null 2>&1; then
    set -- ca-certificates curl tar gzip zstd xdg-utils
    [ "$task_mode" = native ] || set -- "$@" qemu-system-x86
    apt-get update
    apt-get install -y --no-install-recommends "$@"
elif command -v dnf >/dev/null 2>&1; then
    set -- ca-certificates curl tar gzip zstd xdg-utils
    [ "$task_mode" = native ] || set -- "$@" qemu-system-x86-core
    dnf install -y "$@"
elif command -v pacman >/dev/null 2>&1; then
    set -- ca-certificates curl tar gzip zstd xdg-utils
    [ "$task_mode" = native ] || set -- "$@" qemu-system-x86
    pacman -S --needed --noconfirm "$@"
elif command -v zypper >/dev/null 2>&1; then
    set -- ca-certificates curl tar gzip zstd xdg-utils
    [ "$task_mode" = native ] || set -- "$@" qemu-x86
    zypper --non-interactive install "$@"
else
    printf '%s\n' 'Automatic setup supports Ubuntu/Debian, Fedora, Arch and openSUSE.' >&2
    exit 1
fi
if [ "$task_mode" = vm ]; then
    if [ ! -e /dev/kvm ] && command -v modprobe >/dev/null 2>&1; then
        case "$(sed -n 's/^vendor_id[[:space:]]*: //p' /proc/cpuinfo | head -1)" in
            GenuineIntel) modprobe kvm_intel || true ;;
            AuthenticAMD) modprobe kvm_amd || true ;;
        esac
    fi
    if [ -e /dev/kvm ] && getent group kvm >/dev/null && [ "$task_user" != root ]; then
        usermod -a -G kvm -- "$task_user"
    fi
fi
