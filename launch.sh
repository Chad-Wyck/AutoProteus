#!/bin/sh
# One-file Linux launch: bootstrap trusted dependencies, then open guided setup.
set -eu
trap 'task_status=$?; if [ "$task_status" -ne 0 ] && [ -t 0 ]; then printf "%s\n" "Setup needs attention. Press Enter to close, then reopen this file to retry."; read task_acknowledge || true; fi' 0
task_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
cd -- "$task_root"
task_mode=vm
task_previous=
task_acknowledged=no
for task_argument in "$@"; do
    if [ "$task_previous" = --execution ]; then task_mode=$task_argument; fi
    case "$task_argument" in --execution=*) task_mode=${task_argument#*=} ;; esac
    [ "$task_argument" != --acknowledge-host-access ] || task_acknowledged=yes
    task_previous=$task_argument
done
case "$task_mode" in vm|native) ;; *) printf '%s\n' 'Choose VM or explicitly acknowledged native execution.' >&2; exit 2 ;; esac
if [ "$task_mode" = native ] && [ "$task_acknowledged" != yes ]; then
    printf '%s\n' 'Native mode lets model-written code access this account’s files, networks and credentials.' >&2
    printf '%s\n' 'Both --execution native and --acknowledge-host-access are required.' >&2
    exit 2
fi
if [ -L .runtime ]; then
    printf '%s\n' 'The runtime folder must stay inside this project.' >&2
    exit 1
fi
if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
    printf '%s\n' 'This launcher supports 64-bit Intel/AMD Linux desktops.' >&2
    exit 1
fi
printf '%s\n' 'Starting AutoProteus…'
task_setup=no
for task_tool in tar sha256sum zstd xdg-open; do
    command -v "$task_tool" >/dev/null 2>&1 || task_setup=yes
done
if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then task_setup=yes; fi
if [ "$task_mode" = vm ]; then
    [ -x /usr/bin/qemu-system-x86_64 ] || [ -x /usr/local/bin/qemu-system-x86_64 ] || task_setup=yes
    if [ -e /dev/kvm ] && { [ ! -r /dev/kvm ] || [ ! -w /dev/kvm ]; }; then task_setup=yes; fi
fi
if [ "$task_setup" = yes ]; then
    printf '%s\n' 'First-launch setup installs missing Linux components using your system package manager.'
    printf '%s\n' 'VM setup also grants your account access to KVM. Your system may ask for an administrator password.'
    task_user=$(id -un)
    if [ "$(id -u)" = 0 ]; then
        sh "$task_root/controller/linux_setup.sh" "$task_user" "$task_mode"
    elif command -v pkexec >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
        pkexec sh "$task_root/controller/linux_setup.sh" "$task_user" "$task_mode"
    elif command -v sudo >/dev/null 2>&1; then
        sudo -- sh "$task_root/controller/linux_setup.sh" "$task_user" "$task_mode"
    else
        printf '%s\n' 'An administrator is needed to finish dependency setup on this computer.' >&2
        exit 1
    fi
fi
# Apply newly granted KVM access without requiring a sign-out.
if [ "$task_mode" = vm ] && [ -e /dev/kvm ] && { [ ! -r /dev/kvm ] || [ ! -w /dev/kvm ]; }; then
    if command -v sg >/dev/null 2>&1 && id -Gn "$(id -un)" | tr ' ' '\n' | grep -qx kvm; then
        task_quote() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }
        task_restart="exec sh $(task_quote "$task_root/launch.sh")"
        for task_argument in "$@"; do task_restart="$task_restart $(task_quote "$task_argument")"; done
        exec sg kvm -c "$task_restart"
    fi
    printf '%s\n' 'KVM permission needs attention. AutoProteus will explain the next step in setup.'
fi
mkdir -p .runtime .data
task_python="$task_root/.runtime/python-linux/bin/python3"
task_manifest="$task_root/.runtime/python-linux.sha256"
task_sha='d0080766b6b74aeb81e1949ef0d9a20e6c17f7b160fb295a69b936ccb17660be'
task_links_safe() {
    [ ! -L .runtime/python-linux ] || return 1
    find .runtime/python-linux -type l -exec sh -c 'task_prefix=$1; shift; for task_link do task_target=$(readlink -f "$task_link") || exit 1; case "$task_target" in "$task_prefix"/*) ;; *) exit 1 ;; esac; done' sh "$task_root/.runtime/python-linux" {} +
}
task_verified=no
if [ -x "$task_python" ] && [ -f "$task_manifest" ] && [ "$(sed -n '1p' "$task_manifest")" = "# $task_sha" ] && task_links_safe && sha256sum --check --status "$task_manifest"; then
    task_expected=$(($(wc -l < "$task_manifest") - 1))
    task_actual=$(find .runtime/python-linux \( -type f -o -xtype f \) -printf '.' | wc -c)
    [ "$task_expected" -ne "$task_actual" ] || task_verified=yes
fi
if [ "$task_verified" != yes ]; then
    printf '%s\n' 'Preparing private Python (35 MB). No Python installation or pip packages are needed.'
    task_url='https://github.com/astral-sh/python-build-standalone/releases/download/20261013/cpython-3.13.16%2B20261013-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz'
    task_archive="$task_root/.runtime/python-linux-download.tar.gz"
    if [ ! -f "$task_archive" ] || [ "$(sha256sum "$task_archive" | cut -d ' ' -f 1)" != "$task_sha" ]; then
        if command -v curl >/dev/null 2>&1; then
            curl --fail --location --proto '=https' --proto-redir '=https' --retry 2 --output "$task_archive" "$task_url"
        else
            wget --https-only --output-document="$task_archive" "$task_url"
        fi
    fi
    if [ "$(sha256sum "$task_archive" | cut -d ' ' -f 1)" != "$task_sha" ]; then
        printf '%s\n' 'Python download failed its integrity check. Reopen the launcher to retry.' >&2
        exit 1
    fi
    task_stage=$(mktemp -d "$task_root/.runtime/python-linux-stage.XXXXXX")
    tar -xzf "$task_archive" --no-same-owner --no-same-permissions -C "$task_stage"
    if [ -e "$task_root/.runtime/python-linux" ]; then
        mv -- "$task_root/.runtime/python-linux" "$task_root/.runtime/python-linux-incomplete-$$"
    fi
    mv -- "$task_stage/python" "$task_root/.runtime/python-linux"
    rmdir -- "$task_stage"
    rm -- "$task_archive"
    task_links_safe || { printf '%s\n' 'The private Python archive contains an unexpected link.' >&2; exit 1; }
    printf '# %s\n' "$task_sha" > "$task_manifest"
    find .runtime/python-linux \( -type f -o -xtype f \) -print0 | sort -z | xargs -0 sha256sum >> "$task_manifest"
    sha256sum --check --status "$task_manifest" || { printf '%s\n' 'The private Python runtime failed verification.' >&2; exit 1; }
fi
unset PYTHONHOME PYTHONPATH
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
if ! "$task_python" -c 'import sys; assert sys.version_info >= (3, 10)' 2>/dev/null; then
    printf '%s\n' 'The bundled Python cannot run here. A recent glibc-based Linux desktop is required.' >&2
    exit 1
fi
printf '%s\n' 'Opening AutoProteus. Choose a model in setup; the app downloads its engine and weights.'
task_log="$task_root/.data/startup-linux-$(date +%s)-$$.log"
nohup "$task_python" "$task_root/app.py" "$@" >"$task_log" 2>&1 &
task_pid=$!
sleep 1
if ! kill -0 "$task_pid" 2>/dev/null; then
    if wait "$task_pid"; then exit 0; fi
    printf 'AutoProteus could not start. Details: %s\n' "$task_log" >&2
    cat "$task_log" >&2
    exit 1
fi
