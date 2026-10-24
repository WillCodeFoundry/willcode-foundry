# shellcheck shell=bash
# Helpers the git hooks share, so every refusal has the same shape: what was
# wrong, then what to do instead. Sourced, not executed. The hooks source
# task.sh beside it for the task's names.

# refuse <hook> <message...>: print a refusal that says what was wrong and
# what to do instead, then exit non-zero.
refuse() {
    local hook="$1"; shift
    {
        echo "$hook: refusing"
        echo
        printf '  %s\n' "$@"
        echo
    } >&2
    exit 1
}

current_branch() {
    git symbolic-ref --short HEAD 2>/dev/null || echo detached
}
