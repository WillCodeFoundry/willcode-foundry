# shellcheck shell=bash
# Shared helpers for foundry git hooks. Sourced, not executed.
#
# The task's names (TASK_BRANCH, NOTES_BRANCH, TASK_NOTES_RELATIVE_PATH, ...)
# come from lib/task.sh, found next to this file rather than through the
# hook's $0, so it doesn't matter which hook sources this.
# For ShellCheck, relative to the repository root, where CI runs it:
# shellcheck source=agent-kit/lib/task.sh
source "$(dirname "${BASH_SOURCE[0]}")/../../lib/task.sh"

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

# staged_files: paths staged for the commit being made.
staged_files() {
    git diff --cached --name-only --diff-filter=ACMRD
}
