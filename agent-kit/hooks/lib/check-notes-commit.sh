#!/usr/bin/env bash
# Rules for commits on the notes branch (the notes checkout).
#
#   RULE  Only files inside .agent/<your task>/ may change; other tasks'
#         folders belong to other agents.
#   RULE  TASK.md is owned by the human and is never modified by an agent.
set -euo pipefail
source "$(dirname "$0")/common.sh"

outside=()
task_md=()
while IFS= read -r f; do
    case "$f" in
        "$NOTES_DIR"/TASK.md) task_md+=("$f") ;;
        "$NOTES_DIR"/*)       ;;
        *)                    outside+=("$f") ;;
    esac
done < <(staged_files)

if ((${#outside[@]})); then
    refuse pre-commit \
        "On $NOTES_BRANCH you may only change files inside $NOTES_DIR/:" \
        "${outside[@]/#/    }" \
        "" \
        "Other folders belong to other tasks and agents." \
        "Unstage with: git restore --staged <file>"
fi

if ((${#task_md[@]})); then
    refuse pre-commit \
        "$NOTES_DIR/TASK.md is owned by the human and must not be modified." \
        "" \
        "To propose changes, write them to $NOTES_DIR/TASK.proposed.md instead." \
        "Discard your edit with: git restore --staged --worktree $NOTES_DIR/TASK.md"
fi
