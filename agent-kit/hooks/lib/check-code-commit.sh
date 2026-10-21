#!/usr/bin/env bash
# Rules for commits on the task branch (the code checkout).
#
#   RULE  Only code and project documentation go on the task branch.
#   RULE  Task notes (.agent/, TASK.md, PROGRESS.md, LEARNINGS.md) never do.
#   RULE  Credential files are never committed.
set -euo pipefail
source "$(dirname "$0")/common.sh"

notes=()
secrets=()
while IFS= read -r f; do
    case "$f" in
        .agent/*|*/.agent/*|TASK.md|PROGRESS.md|LEARNINGS.md|*/TASK.md|*/PROGRESS.md|*/LEARNINGS.md)
            notes+=("$f") ;;
        .env|.env.*|*/.env|*/.env.*|*.pem|*.key|*_rsa|*_ed25519|*.p12|*.pfx)
            secrets+=("$f") ;;
    esac
done < <(staged_files)

if ((${#notes[@]})); then
    refuse pre-commit \
        "Task notes do not belong on $TASK_BRANCH:" \
        "${notes[@]/#/    }" \
        "" \
        "Move them to \$AGENT_NOTES_DIR/$NOTES_DIR/ and commit there on $NOTES_BRANCH." \
        "Unstage with: git restore --staged <file>"
fi

if ((${#secrets[@]})); then
    refuse pre-commit \
        "These look like credential files and must never be committed:" \
        "${secrets[@]/#/    }" \
        "" \
        "Unstage with: git restore --staged <file>" \
        "If a file is genuinely not a credential, rename it so it does not match."
fi
