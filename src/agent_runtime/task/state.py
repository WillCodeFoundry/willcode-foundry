"""A task state: a task's STATE.json, which says which state of its lifecycle the task is in.

The file holds exactly three keys: ``lifecycle``, ``state`` and ``note``. Its history is the file's git log on the
notes branch, which also says which state the task came from. This module only reads, checks and changes task
states, with no git and no files. The runtime's ``task`` command and foundry do the git around it.

Shared with foundry (ARCHITECTURE.md, design rule 2).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Final

from agent_runtime.agent_kit import TASK_COMMAND
from agent_runtime.task.lifecycles import LIFECYCLES, Event, Lifecycle, State

STATE_FILE: Final = "STATE.json"
"""A task's task state, in its task notes dir. Spelled here only; state_path builds on it."""


def state_path(task_notes_dir: str) -> str:
    """Where a task's STATE.json sits, relative to the repository root, given its task notes dir."""
    return f"{task_notes_dir}/{STATE_FILE}"


END_TURN: Final = f'{TASK_COMMAND} <event> "<hand-off note>"'
"""How an agent sends the event that writes its next task state, as every message that tells it to spells it."""

_KEYS: Final = ("lifecycle", "state", "note")

_NO_NOTE: Final = "Give a hand-off note. Say what whoever is next should read first."


class TaskStateRefused(Exception):
    """A task state can't be read or changed as asked. The message says what is wrong and which rule it breaks."""


@dataclass(frozen=True, kw_only=True)
class TaskState:
    """A task's lifecycle, the state it is in, and the hand-off note it was left."""

    lifecycle: Lifecycle
    state: str
    note: str

    @classmethod
    def new(cls, lifecycle: Lifecycle) -> "TaskState":
        """A new task's state: its lifecycle's initial state, with no hand-off note yet."""
        return cls(lifecycle=lifecycle, state=lifecycle.initial, note="")

    @classmethod
    def parse(cls, text: str, where: str) -> "TaskState":
        """Read a STATE.json's text; TaskStateRefused naming ``where`` if it isn't a task state."""
        try:
            fields = json.loads(text)
        except json.JSONDecodeError as error:
            raise TaskStateRefused(f"{where} is not valid JSON: {error}") from None
        if not isinstance(fields, dict) or set(fields) != set(_KEYS):
            raise TaskStateRefused(f"{where} is not a task state. It must hold exactly {', '.join(_KEYS)}.")
        lifecycle = LIFECYCLES.get(fields["lifecycle"]) if isinstance(fields["lifecycle"], str) else None
        if lifecycle is None:
            raise TaskStateRefused(
                f"{where} names no known lifecycle, {fields['lifecycle']!r}. "
                f"The lifecycles are {', '.join(LIFECYCLES)}."
            )
        if not isinstance(fields["state"], str) or fields["state"] not in lifecycle.states:
            raise TaskStateRefused(f"{where}: state {fields['state']!r} is not a state of {lifecycle.name}")
        if not isinstance(fields["note"], str):
            raise TaskStateRefused(f"{where}: note must be text")
        return cls(lifecycle=lifecycle, state=fields["state"], note=fields["note"])

    def to_json(self) -> str:
        """The STATE.json text: the three keys in order, two-space indented, ending with a newline."""
        fields: dict[str, Any] = {
            "lifecycle": self.lifecycle.name,
            "state": self.state,
            "note": self.note,
        }
        return json.dumps(fields, indent=2, ensure_ascii=False) + "\n"

    @property
    def _definition(self) -> State:
        """The state the task is in, as its lifecycle defines it."""
        return self.lifecycle.states[self.state]

    @property
    def goal(self) -> str:
        """What the turn in this state is for; empty for a terminal state."""
        return self._definition.goal

    @property
    def events(self) -> Mapping[str, Event]:
        """The events that end the turn in this state, by name; none for a terminal state."""
        return self._definition.events

    @property
    def role(self) -> str | None:
        """The role whose turn it is; None in a terminal state."""
        return self._definition.role

    @property
    def terminal(self) -> bool:
        """Whether no event leaves the state the task is in, such as blocked or done."""
        return self._definition.terminal

    @property
    def blocked(self) -> bool:
        """Whether the task waits for a human to answer its note and move it on."""
        return self._definition.blocked

    @property
    def standing(self) -> str:
        """Who works on the task now, as a sentence: its role, a human, or no one."""
        if self.role:
            return f"It is assigned to the {self.role}."
        return "It waits for a human." if self.blocked else "No role works on it."

    def after(self, event: str, note: str, role: str) -> "TaskState":
        """The task state once ``role`` sends ``event`` with a hand-off note; TaskStateRefused saying why not.

        This is the transition rule. The task command applies it to an event, and pre-push to what a push changes,
        through event_to (ADR 0011).
        """
        if self.role != role:
            raise TaskStateRefused(f"The {role} can't send events in {self.state}. {self.standing}")
        events = self.events
        if event not in events:
            raise TaskStateRefused(
                f"{self.state} doesn't accept {event!r}. Send one of {', '.join(events)} (see {TASK_COMMAND} show)."
            )
        return self._moved(events[event].target, note)

    def event_to(self, state: str) -> str:
        """The event that leads from this state to ``state``; TaskStateRefused when none does.

        Two events leading to one state give the same task state, so either will do.
        """
        if leading := [name for name, event in self.events.items() if event.target == state]:
            return leading[0]
        if targets := sorted({event.target for event in self.events.values()}):
            raise TaskStateRefused(f"{self.state} can't go to {state}. Its events lead to {', '.join(targets)}.")
        raise TaskStateRefused(f"{self.state} can't go to {state}. No event leaves it. {self.standing}")

    def moved(self, to: str, note: str) -> "TaskState":
        """The task state moved by hand to any state of its lifecycle; TaskStateRefused for one it lacks."""
        if to not in self.lifecycle.states:
            raise TaskStateRefused(
                f"{self.lifecycle.name} has no state {to!r}. Its states are {', '.join(self.lifecycle.states)}."
            )
        return self._moved(to, note)

    def _moved(self, to: str, note: str) -> "TaskState":
        if not note.strip():
            raise TaskStateRefused(_NO_NOTE)
        return replace(self, state=to, note=note.strip())


def commit_subject(task_id: str, from_state: str, to_state: str, cause: str) -> str:
    """The subject of the commit that moves a task from ``from_state`` to ``to_state``, and the event or other
    ``cause``. The file's history reads as these subjects."""
    return f"{task_id}: {from_state} → {to_state} ({cause})"
