"""Task states on the host: reading them from a project's notes branch, and moving a task by hand.

A task state is the STATE_FILE in a task's notes folder; its lifecycle is a state machine in
agent-kit/lifecycle/ (see agent-kit/bin/task for the format). Agents move tasks only with the kit's
bin/task, which alone applies events and their rules; foundry never does.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from foundry import paths
from foundry.errors import FoundryError
from foundry.git_clone import GitClone
from foundry.task import NOTES_BRANCH, NOTES_ROOT, STATE_FILE, Task

HUMAN: Final = "human"


@dataclass(frozen=True, kw_only=True)
class TaskState:
    """A task's STATE_FILE, as bin/task writes it."""

    lifecycle: str
    state: str
    previous: str | None
    counts: Mapping[str, int]
    """How many times each limited event has gone to its target, by "<state>.<event>"."""
    commit: str
    """The task branch's pushed head when the state was last set by an agent."""
    note: str
    """The hand-off note for whoever's turn it is."""

    @classmethod
    def parse(cls, text: str, where: str) -> "TaskState":
        """Read a STATE_FILE's text; raise FoundryError naming ``where`` if it isn't one."""
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as error:
            raise FoundryError(f"{where}: not valid JSON: {error}") from None
        if not (
            isinstance(raw, dict)
            and set(raw) == {"lifecycle", "state", "previous", "counts", "handoff"}
            and isinstance(raw["lifecycle"], str)
            and isinstance(raw["state"], str)
            and (raw["previous"] is None or isinstance(raw["previous"], str))
            and isinstance(raw["counts"], dict)
            and all(isinstance(key, str) and type(count) is int and count >= 0 for key, count in raw["counts"].items())
            and isinstance(raw["handoff"], dict)
            and set(raw["handoff"]) == {"commit", "note"}
            and all(isinstance(value, str) for value in raw["handoff"].values())
        ):
            raise FoundryError(f"{where}: not a task state: it needs lifecycle, state, previous, counts and handoff")
        return cls(
            lifecycle=raw["lifecycle"],
            state=raw["state"],
            previous=raw["previous"],
            counts=dict(raw["counts"]),
            commit=raw["handoff"]["commit"],
            note=raw["handoff"]["note"],
        )

    def to_json(self) -> str:
        """The STATE_FILE's text, laid out as bin/task writes it."""
        raw = {
            "lifecycle": self.lifecycle,
            "state": self.state,
            "previous": self.previous,
            "counts": dict(self.counts),
            "handoff": {"commit": self.commit, "note": self.note},
        }
        return json.dumps(raw, indent=2, ensure_ascii=False) + "\n"


@dataclass(frozen=True)
class Lifecycle:
    """A lifecycle's states, by name: as much of it as the host needs, which is who each state is assigned."""

    name: str
    states: Mapping[str, Mapping[str, Any]]
    on: Mapping[str, Any]
    """The top-level events, which every role's state accepts."""

    def assignee(self, state: str) -> str | None:
        """The role whose turn ``state`` is, or HUMAN; None for a final state."""
        if state not in self.states:
            raise FoundryError(f"lifecycle {self.name} has no state {state!r}; its states: {', '.join(self.states)}")
        assignee = self.states[state].get("assignee")
        return assignee if isinstance(assignee, str) else None


def lifecycle_problem(lifecycle: Any) -> str | None:
    """What keeps ``lifecycle`` from being one bin/task can apply, or None.

    The same checks as bin/task's lifecycle_problem, which tests/test_task_state_parity.py holds the two to.
    """
    if not isinstance(lifecycle, dict):
        return "it isn't a JSON object"
    states = lifecycle.get("states")
    if not isinstance(states, dict) or not states:
        return "it has no states"
    tables = {"the top level": lifecycle.get("on", {})}
    for name, definition in states.items():
        if not isinstance(definition, dict):
            return f"state {name} isn't an object"
        tables[f"state {name}"] = definition.get("on", {})
    for where, on in tables.items():
        if not isinstance(on, dict):
            return f"{where}'s on isn't an object"
        for event, transition in on.items():
            if not (
                isinstance(transition, dict)
                and isinstance(transition.get("target"), str)
                and isinstance(transition.get("when"), str)
            ):
                return f"{where}'s {event} needs a target and a when"
            if "limit" in transition and not (type(transition["limit"]) is int and transition["limit"] >= 1):
                return f"{where}'s {event} has a limit that isn't a whole number from 1"
            for key in ("target", "fallback"):
                if key in transition and (not isinstance(transition[key], str) or transition[key] not in states):
                    return f"{where}'s {event} has a {key} that isn't one of its states"
    return None


def load_lifecycle(foundry_root: Path, name: str) -> Lifecycle:
    path = paths.lifecycle_path(foundry_root, name)
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError:
        raise FoundryError(f"lifecycle {name!r} has no file {path}") from None
    except json.JSONDecodeError as error:
        raise FoundryError(f"{path} is not valid JSON: {error}") from None
    problem = lifecycle_problem(raw)
    if problem:
        raise FoundryError(f"{path} is not a lifecycle: {problem}")
    return Lifecycle(name=name, states=raw["states"], on=raw.get("on", {}))


# --- reading from the notes branch ---------------------------------------------------


def read(clone: GitClone, task: Task) -> TaskState | None:
    """The task's state, from ``clone`` with NOTES_BRANCH checked out; None for a task created before task states."""
    if not clone.exists(task.notes_dir):
        raise FoundryError(f"there is no task {task.id}: {NOTES_BRANCH} has no {task.notes_dir}/")
    text = clone.read(task.state_file)
    return None if text is None else TaskState.parse(text, task.state_file)


def read_all(clone: GitClone) -> dict[str, TaskState | FoundryError | None]:
    """Every task's state, by task id in order, from ``clone`` with NOTES_BRANCH checked out.

    A task whose state can't be read gets the error instead, so one bad task doesn't hide the others.
    """
    task_ids = [path.removeprefix(f"{NOTES_ROOT}/") for path in clone.folders(f"{NOTES_ROOT}/*")]
    states: dict[str, TaskState | FoundryError | None] = {}
    for task_id in task_ids:
        try:
            states[task_id] = read(clone, Task(task_id))
        except FoundryError as error:
            states[task_id] = error
    return states


# --- what's next -----------------------------------------------------------------------


def next_role(state: TaskState | None, lifecycle: Lifecycle | None, task: Task, *, project_name: str) -> str:
    """The role whose turn it is; FoundryError saying what to do when it is no role's.

    ``lifecycle`` is the state's, and None only with no state.
    """
    if state is None or lifecycle is None:
        raise FoundryError(
            f"task {task.id} has no {STATE_FILE}: it was created before task states, so it has no turns; "
            f"launch a role with: foundry task run {project_name} {task.id} ROLE"
        )
    assignee = lifecycle.assignee(state.state)
    if assignee is None:
        raise FoundryError(
            f"task {task.id} is done; to reopen it: foundry task move {project_name} {task.id} STATE --note …"
        )
    if assignee == HUMAN:
        came_from = f" (from {state.previous})" if state.previous else ""
        back = state.previous or "STATE"
        raise FoundryError(
            f"task {task.id} is waiting for you, in {state.state}{came_from}: {state.note or '(no note)'}\n"
            f"  once you've answered, hand it back: foundry task move {project_name} {task.id} {back} --note …\n"
            "  or move it anywhere else in its lifecycle; the README's Task states section lists the usual moves"
        )
    return assignee
