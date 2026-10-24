# shellcheck shell=bash
# A task's names, from its id in $AGENT_TASK: the agent kit's equivalent of
# Task in src/foundry/task.py, which must agree with it, as must the rulesets
# in config/repo-policy/rulesets.yaml. tests/test_task_contract.py checks that
# all three do. Sourced, not executed.
#
# The variables are used by the scripts that source it, which ShellCheck can't see from here.
# shellcheck disable=SC2034

: "${AGENT_TASK:?AGENT_TASK is not set; the agent kit only runs inside a foundry session}"

TASK_BRANCH="task/$AGENT_TASK"                                # where the task's code is written
NOTES_BRANCH="agent-notes"                                    # every task's notes, each in its own folder
TASK_NOTES_RELATIVE_PATH=".agent/$AGENT_TASK"                 # this task's folder on $NOTES_BRANCH
TASK_FILE_RELATIVE_PATH="$TASK_NOTES_RELATIVE_PATH/TASK.md"   # the TASK.md every task has
