"""The rules of Claude Code's hooks. agent_runtime.commands.claude_hook reads the hook's JSON and writes its reply.

``refusal_reason`` is guard-bash's rule (PreToolUse, on Bash): a command must not skip or reconfigure the git hooks.
session-check's (Stop) is agent_runtime.unsaved_work's: the agent may not stop while either checkout has unsaved
work, or can't be checked.
Both are guardrails against mistakes, not boundaries: see docs/security-model.md. Both trust the
environment Claude Code gives them, which a settings file the agent writes can change.
"""

import re
import shlex

_NO_VERIFY = re.compile(r"(?<![\w-])--no-verify(?![\w-])")
_QUOTING = re.compile(r"['\"\\]")
_SHELL_PUNCTUATION = "()$`;&|<>{}"
_BYPASS_REASON = "git hooks must not be bypassed (--no-verify)"
_RECONFIGURE_REASON = "git hook configuration must not be changed"


def refusal_reason(command: str) -> str | None:
    """Why ``command`` is refused, or None.

    Refuses a word that is --no-verify once shell punctuation is stripped, so ``$(git commit --no-verify)``
    counts, or that mentions core.hooksPath. A quoted word stays one word, so a commit message that mentions
    --no-verify passes. Nothing is dropped: a heredoc's body can run. What shlex can't split, a comment's
    apostrophe say, is scanned whole with its quoting removed. Accepted misses, on purpose, to keep this simple:
    ``git commit -n``, abbreviations such as --no-ver, --no-verify inside ``sh -c "..."``, and
    ``git config --get core.hooksPath`` being refused although it only reads.
    """
    try:
        words = [word.strip(_SHELL_PUNCTUATION) for word in shlex.split(command)]
    except ValueError:  # unbalanced quotes, an apostrophe in prose say: scan the whole text, unquoted
        return _refusal_reason_in_text(_QUOTING.sub("", command))
    if "--no-verify" in words:
        return _BYPASS_REASON
    if any("core.hookspath" in word.lower() for word in words):
        return _RECONFIGURE_REASON
    return None


def _refusal_reason_in_text(text: str) -> str | None:
    if _NO_VERIFY.search(text):
        return _BYPASS_REASON
    if "core.hookspath" in text.lower():
        return _RECONFIGURE_REASON
    return None
