"""A task state: a task's STATE.json, which says which state of its lifecycle the task is in.

The file holds exactly four keys: ``lifecycle``, ``state``, ``previous`` and ``note``. Its history is the file's
git log on the notes branch. This module only reads, checks and changes task states: no git, no files. The
runtime's ``task`` command and foundry do the git around it.

Shared with foundry (ARCHITECTURE.md, design rule 2).
"""

import json
from dataclasses import dataclass, replace
from typing import Any, Final

from agent_runtime.agent_kit import TASK_COMMAND
from agent_runtime.task.lifecycles import HUMAN, LIFECYCLES, Lifecycle, State

STATE_FILE: Final = "STATE.json"
"""A task's task state, in its task notes dir. Spelled here only; state_path builds on it."""


def state_path(task_notes_dir: str) -> str:
    """Where a task's STATE.json sits, relative to the repository root, given its task notes dir."""
    return f"{task_notes_dir}/{STATE_FILE}"


END_TURN: Final = f'{TASK_COMMAND} <event> "<hand-off note>"'
"""How an agent ends its turn, as every message that tells it to spells it."""

_KEYS: Final = ("lifecycle", "state", "previous", "note")


class TaskStateRefused(Exception):
    """A task state can't be read or changed as asked; the message says why, and what to do instead."""


@dataclass(frozen=True, kw_only=True)
class TaskState:
    """A task's lifecycle, the state it is in, the state it came from, and the hand-off note it was left."""

    lifecycle: Lifecycle
    state: str
    previous: str | None
    note: str

    @classmethod
    def new(cls, lifecycle: Lifecycle) -> "TaskState":
        """A new task's state: its lifecycle's initial state, with no hand-off note yet."""
        return cls(lifecycle=lifecycle, state=lifecycle.initial, previous=None, note="")

    @classmethod
    def parse(cls, text: str, where: str) -> "TaskState":
        """Read a STATE.json's text; TaskStateRefused naming ``where`` if it isn't a task state."""
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as error:
            raise TaskStateRefused(f"{where} is not valid JSON: {error}") from None
        if not isinstance(raw, dict) or set(raw) != set(_KEYS):
            raise TaskStateRefused(f"{where} is not a task state: it must hold exactly {', '.join(_KEYS)}")
        lifecycle = LIFECYCLES.get(raw["lifecycle"]) if isinstance(raw["lifecycle"], str) else None
        if lifecycle is None:
            raise TaskStateRefused(
                f"{where} names no known lifecycle: {raw['lifecycle']!r}; the lifecycles: {', '.join(LIFECYCLES)}"
            )
        for key in ("state", "previous"):
            value = raw[key]
            if key == "previous" and value is None:
                continue
            if not isinstance(value, str) or value not in lifecycle.states:
                raise TaskStateRefused(f"{where}: {key} {value!r} is not a state of {lifecycle.name}")
        if not isinstance(raw["note"], str):
            raise TaskStateRefused(f"{where}: note must be text")
        return cls(lifecycle=lifecycle, state=raw["state"], previous=raw["previous"], note=raw["note"])

    def to_json(self) -> str:
        """The STATE.json text: the four keys in order, two-space indented, ending with a newline."""
        raw: dict[str, Any] = {
            "lifecycle": self.lifecycle.name,
            "state": self.state,
            "previous": self.previous,
            "note": self.note,
        }
        return json.dumps(raw, indent=2, ensure_ascii=False) + "\n"

    @property
    def definition(self) -> State:
        """The state the task is in, as its lifecycle defines it."""
        return self.lifecycle.states[self.state]

    @property
    def turn(self) -> str | None:
        """Whose turn it is: a role, HUMAN, or None once the task is done."""
        return self.definition.assignee

    @property
    def role(self) -> str | None:
        """The role whose turn it is; None when it is the human's, or no one's once the task is done."""
        return None if self.turn in (None, HUMAN) else self.turn

    @property
    def waits_for_human(self) -> bool:
        """Whether it is the human's turn."""
        return self.turn == HUMAN

    @property
    def whose(self) -> str:
        """Whose turn it is, as a sentence says it: "the dev's", "the human's", or "no one's"."""
        return "no one's" if self.turn is None else f"the {self.turn}'s"

    def after(self, event: str, note: str) -> "TaskState":
        """The task state once ``event`` is sent with a hand-off note; TaskStateRefused saying why not.

        Whose turn it is isn't checked here: launch checks it, and pre-push guards the change (ADR 0011).
        """
        events = self.definition.events
        if not events:
            raise TaskStateRefused(f"{self.state} accepts no events")
        if event not in events:
            raise TaskStateRefused(
                f"{self.state} doesn't accept {event!r}: send one of {', '.join(events)} (see {TASK_COMMAND} show)"
            )
        return self._moved(events[event].target, note)

    def moved(self, to: str, note: str) -> "TaskState":
        """The task state moved by hand to any state of its lifecycle; TaskStateRefused for one it lacks."""
        if to not in self.lifecycle.states:
            raise TaskStateRefused(
                f"{self.lifecycle.name} has no state {to!r}; its states: {', '.join(self.lifecycle.states)}"
            )
        return self._moved(to, note)

    def _moved(self, to: str, note: str) -> "TaskState":
        if not note.strip():
            raise TaskStateRefused("give a hand-off note: what the next assignee should read first")
        return replace(self, state=to, previous=self.state, note=note.strip())


def legal_change(old: TaskState, new: TaskState, role: str) -> str | None:
    """Why going from ``old`` to ``new`` isn't a transition ``role`` may make, or None if it is one.

    A legal change keeps the lifecycle, is made on the role's turn, goes where one of the state's events leads,
    records the state it left as ``previous``, and leaves a hand-off note. It needn't say which event it was.
    """
    if new.lifecycle != old.lifecycle:
        return f"the lifecycle changed from {old.lifecycle.name} to {new.lifecycle.name}"
    if old.turn != role:
        return f"it is {old.whose} turn, not the {role}'s: the task is in {old.state}"
    targets = {event.target for event in old.definition.events.values()}
    if new.state not in targets:
        return f"{old.state} can't go to {new.state}: its events lead to {', '.join(sorted(targets))}"
    if new.previous != old.state:
        return f"previous must be {old.state}, the state it left, not {new.previous}"
    if not new.note.strip():
        return "the hand-off note is empty"
    return None
