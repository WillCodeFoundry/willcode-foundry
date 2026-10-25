# shellcheck shell=bash
# The checks that make a sandbox hardened: the agent can't become root and
# can't change Claude's managed settings. Sourced by `session-harden --verify`,
# which runs them as the agent itself, with the groups sbx gives it; root, or
# a login through su, would see different permissions. Sourced, not executed.
#
# Each check takes what it inspects as arguments, so the tests can point it at
# files of their own. On failure it prints what the agent can still do, one
# line, and returns 1.

# hardening_check_sudo: the agent can't run sudo.
hardening_check_sudo() {
    if sudo -n true >/dev/null 2>&1; then
        echo "run sudo"
        return 1
    fi
}

# hardening_check_su: the agent can't su to root. Root's password is locked, so
# su fails even without a terminal, and succeeds without one if root has none.
hardening_check_su() {
    if su root -c true </dev/null >/dev/null 2>&1; then
        echo "su to root"
        return 1
    fi
}

# hardening_check_docker_sockets <socket>...: the agent can't write to any of
# these sockets. Reaching dockerd is root over the sandbox: it mounts the
# sandbox's own filesystem for anyone who can run a container.
hardening_check_docker_sockets() {
    local socket failed=1
    for socket in "$@"; do
        if [[ -S "$socket" && -w "$socket" ]]; then
            echo "use $socket, which is root over this sandbox"
            failed=0
        fi
    done
    ((failed))
}

# hardening_check_managed_settings <installed> <kit copy> [owner uid]: the
# installed settings exist, belong to the owner (root unless given), can't be
# written by the agent, and are the kit's. Settings from an older kit mean older
# permissions and hooks, so they count as not hardened.
hardening_check_managed_settings() {
    local installed="$1" kit_copy="$2" owner="${3:-0}"
    if [[ ! -f "$installed" ]]; then
        echo "run without Claude's managed settings: $installed is missing"
        return 1
    fi
    if [[ "$(stat -c %u "$installed")" != "$owner" ]]; then
        echo "replace Claude's managed settings: $installed isn't owned by uid $owner"
        return 1
    fi
    if [[ -w "$installed" ]]; then
        echo "change Claude's managed settings: $installed is writable"
        return 1
    fi
    if ! cmp -s "$installed" "$kit_copy"; then
        echo "run with older managed settings: $installed differs from $kit_copy"
        return 1
    fi
}
