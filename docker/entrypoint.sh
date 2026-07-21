#!/bin/sh
set -eu

HOME="${HOME:-/home/dsa}"
DATA_CACHE_DIR="${DATA_CACHE_DIR:-/app/data/cache}"
export HOME

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

assert_writable_dir() {
    dir="$1"
    mkdir -p "$dir" 2>/dev/null || fail "required runtime directory is not creatable: $dir"
    [ -w "$dir" ] || fail "required runtime directory is not writable: $dir"

    probe="$dir/.dsa-write-check.$$"
    if ! (: > "$probe") 2>/dev/null; then
        fail "required runtime directory failed its write probe: $dir"
    fi
    rm -f "$probe" 2>/dev/null || fail "runtime write probe could not be removed: $dir"
}

assert_writable_dir "$HOME"
assert_writable_dir "$HOME/.longbridge"
assert_writable_dir /app/data
assert_writable_dir "$DATA_CACHE_DIR"
assert_writable_dir /app/logs
assert_writable_dir /app/reports

exec "$@"
