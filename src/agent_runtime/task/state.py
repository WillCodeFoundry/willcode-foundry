"""A task state: a task's STATE.json, which says which state of its lifecycle the task is in.

The file holds exactly four keys: ``lifecycle``, ``state``, ``previous`` and ``note``. Its history is the file's
git log on the notes branch. This module only reads, checks and changes task states: no git, no files. The
runtime's ``task`` command and foundry do the git around it.

Shared with foundry (ARCHITECTURE.md, design rule 2).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Final

from agent_runtime.agent_kit import TASK_COMMAND
from agent_runtime.task.lifecycles import HUMAN, LIFECYCLES, Event, Lifecycle, State

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
            raise TaskStateRefused(f"{where} is not a task state. It must hold exactly {', '.join(_KEYS)}.")
        lifecycle = LIFECYCLES.get(raw["lifecycle"]) if isinstance(raw["lifecycle"], str) else None
        if lifecycle is None:
            raise TaskStateRefused(
                f"{where} names no known lifecycle, {raw['lifecycle']!r}. The lifecycles are {', '.join(LIFECYCLES)}."
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
    def _definition(self) -> State:
        """The state the task is in, as its lifecycle defines it."""
        return self.lifecycle.states[self.state]

    @property
    def goal(self) -> str:
        """What the turn in this state is for; empty for the human's or a final state."""
        return self._definition.goal

    @property
    def events(self) -> Mapping[str, Event]:
        """The events that end the turn in this state, by name; none for the human's or a final state."""
        return self._definition.events

    @property
    def assignee(self) -> str | None:
        """The assignee of the state the task is in: a role, HUMAN, or None once the task is done."""
        return self._definition.assignee

    @property
    def role(self) -> str | None:
        """The role whose turn it is. None when the task is assigned to the human, or to no one once it is done."""
        return None if self.assignee in (None, HUMAN) else self.assignee

    @property
    def assigned_to_human(self) -> bool:
        """Whether the task waits for the human, as blocked does."""
        return self.assignee == HUMAN

    @property
    def assignee_named(self) -> str:
        """The assignee as a sentence names it: "the dev", "the human", or "no one"."""
        return "no one" if self.assignee is None else f"the {self.assignee}"

    def after(self, event: str, note: str) -> "TaskState":
        """The task state once ``event`` is sent with a hand-off note; TaskStateRefused saying why not.

        Whose turn it is isn't checked here. Launch checks it, and pre-push guards the change (ADR 0011).
        """
        events = self._definition.events
        if not events:
            raise TaskStateRefused(f"{self.state} accepts no events")
        if event not in events:
            raise TaskStateRefused(
                f"{self.state} doesn't accept {event!r}. Send one of {', '.join(events)} (see {TASK_COMMAND} show)."
            )
        return self._moved(events[event].target, note)

    def moved(self, to: str, note: str) -> "TaskState":
        """The task state moved by hand to any state of its lifecycle; TaskStateRefused for one it lacks."""
        if to not in self.lifecycle.states:
            raise TaskStateRefused(
                f"{self.lifecycle.name} has no state {to!r}. Its states are {', '.join(self.lifecycle.states)}."
            )
        return self._moved(to, note)

    def commit_subject(self, task_id: str, cause: str) -> str:
        """The subject of the commit that moved the task here: where from, where to, and the event or other
        ``cause``."""
        return f"{task_id}: {self.previous} → {self.state} ({cause})"

    def _moved(self, to: str, note: str) -> "TaskState":
        if not note.strip():
            raise TaskStateRefused("Give a hand-off note. Say what the next assignee should read first.")
        return replace(self, state=to, previous=self.state, note=note.strip())
