#!/bin/sh
# Linux launcher. Execution stays VM-only unless the user supplies both native flags.
set -eu
cd -- "$(dirname -- "$0")"
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'AutoProteus needs Python 3.10 or newer.' >&2
    exit 1
fi
exec python3 app.py "$@"
