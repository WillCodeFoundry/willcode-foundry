#!/usr/bin/env bash
# Rules for commit messages, from either checkout. git passes the path of the
# file holding the message as $1.
#
#   RULE  Commit messages carry no Co-Authored-By trailer or tool attribution line.
#   RULE  Commits on the task branch end with a "Task: <your task>" trailer.
set -euo pipefail
source "$(dirname "$0")/common.sh"

msg_file="${1:?commit-msg hook needs the message file}"
# Ignore the comment lines git adds when the message is written in an editor.
message=$(git stripspace --strip-comments < "$msg_file")
trailers=$(git interpret-trailers --parse <<<"$message")

if grep -qi '^co-authored-by:' <<<"$trailers"; then
    refuse commit-msg \
        "Commit messages must not carry a Co-Authored-By trailer." \
        "Remove it and commit again; see \$AGENT_KIT_DIR/skills/git-conventions/SKILL.md."
fi

if grep -Eqi 'generated (with|by) .*claude' <<<"$message"; then
    refuse commit-msg \
        "Commit messages must not carry a tool attribution line (\"Generated with ...\")." \
        "Remove it and commit again."
fi

if [[ "$(current_branch)" == "$TASK_BRANCH" ]] && ! grep -qx "Task: $AGENT_TASK" <<<"$trailers"; then
    refuse commit-msg \
        "Commits on $TASK_BRANCH must end with the trailer:" \
        "    Task: $AGENT_TASK" \
        "" \
        "Add it as the last paragraph of the message, for example:" \
        "    git commit -m \"feat(scope): summary\" -m \"Why.\" -m \"Task: $AGENT_TASK\""
fi
