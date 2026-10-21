#!/usr/bin/env bash
# Rules for pushes from either checkout. Reads the ref lines git passes to
# pre-push on stdin: <local ref> <local sha> <remote ref> <remote sha>
#
#   RULE  Only task/<your task> and agent-notes may be pushed.
#   RULE  Remote branches are never deleted.
#   RULE  Pushed history is never rewritten: every push is a fast-forward.
set -euo pipefail
source "$(dirname "$0")/common.sh"

zero="0000000000000000000000000000000000000000"

while read -r local_ref local_sha remote_ref remote_sha; do
    branch="${remote_ref#refs/heads/}"

    if [[ "$local_sha" == "$zero" ]]; then
        refuse pre-push \
            "Deleting remote branch $branch is not allowed." \
            "If it must go, record the request under Blockers and ask."
    fi

    case "$branch" in
        "$TASK_BRANCH"|"$NOTES_BRANCH") ;;
        *)
            refuse pre-push \
                "You may only push $TASK_BRANCH and $NOTES_BRANCH, not $branch." \
                "Code goes on $TASK_BRANCH; notes go on $NOTES_BRANCH."
            ;;
    esac

    if [[ "$remote_sha" != "$zero" ]] \
       && ! git merge-base --is-ancestor "$remote_sha" "$local_sha" 2>/dev/null; then
        refuse pre-push \
            "This push would rewrite history on $branch (not a fast-forward)." \
            "" \
            "Never force-push or rebase pushed commits." \
            "If the remote has moved, run: git pull --rebase origin $branch" \
            "then push again. If that conflicts, record it under Blockers and ask."
    fi
done
