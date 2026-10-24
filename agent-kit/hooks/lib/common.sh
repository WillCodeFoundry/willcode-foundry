# shellcheck shell=bash
# Shared helpers for foundry git hooks. Sourced, not executed.
# Its variables are used by the hooks that source it, which ShellCheck can't see from here.
# shellcheck disable=SC2034

: "${AGENT_TASK:?AGENT_TASK is not set; hooks only run inside a foundry session}"

TASK_BRANCH="task/$AGENT_TASK"
NOTES_BRANCH="agent-notes"
TASK_NOTES_RELATIVE_PATH=".agent/$AGENT_TASK"

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
