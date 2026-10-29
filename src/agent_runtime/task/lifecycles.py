"""The lifecycles: the state machine each kind of task follows, written once, as data in Python.

A lifecycle's states each name their assignee: a role, HUMAN, or None for a final state. A role's state also
names its goal and its events, each with the state it leads to and when to send it. Every role's state accepts
BLOCK, which hands the task to the human. Skills are not named here: an agent picks among its role's skills.

Shared with foundry, which reads lifecycles to launch whoever's turn it is (ARCHITECTURE.md, design rule 2).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

HUMAN: Final = "human"
"""The assignee of a state that is yours: you move the task on with `foundry task move`."""

BLOCK: Final = "block"
"""The event every role's state accepts: hand the task to the human with a question."""


@dataclass(frozen=True)
class Event:
    """What an agent sends to end its turn: the state it leads to, and when to send it."""

    target: str
    when: str


@dataclass(frozen=True)
class State:
    """One step of a lifecycle. A role's state has a goal and events; a human or final state has neither."""

    assignee: str | None
    """A role, HUMAN, or None for a final state."""
    goal: str = ""
    events: Mapping[str, Event] = field(default_factory=dict)


@dataclass(frozen=True)
class Lifecycle:
    """A named state machine. tests/agent_runtime/test_lifecycles.py holds every lifecycle to the rules of its
    form."""

    name: str
    initial: str
    states: Mapping[str, State]


_BLOCKED: Final = "blocked"
_BLOCK_EVENT: Final = Event(_BLOCKED, "you need the human to decide something: put the question in the note")


def _role_state(assignee: str, goal: str, **events: Event) -> State:
    """A role's state: its own events, then BLOCK."""
    return State(assignee, goal, {**events, BLOCK: _BLOCK_EVENT})


_IMPLEMENT: Final = _role_state(
    "dev",
    "Implement TASK.md, or answer the latest REVIEW.md round if it asks for changes.",
    submit=Event(
        "review", "every acceptance criterion is met, or every open finding is answered, and the code is pushed"
    ),
)
_REVIEW: Final = _role_state(
    "reviewer",
    "Review the task branch and write a round in REVIEW.md.",
    approve=Event("deliver", "the round's verdict is approved"),
    reject=Event("implement", "the round's verdict is changes needed"),
)
_DELIVER: Final = _role_state(
    "dev",
    "Open the pull request for the approved branch.",
    submit=Event("done", "the pull request is open: put its URL in the note"),
)
_ENDS: Final = {_BLOCKED: State(HUMAN), "done": State(None)}

FEATURE: Final = Lifecycle(
    name="feature",
    initial="plan",
    states={
        "plan": _role_state(
            "planner",
            "Draft TASK.md with the human, and write it once they approve.",
            submit=Event("implement", "the human approved the draft, and it is written and pushed"),
        ),
        "implement": _IMPLEMENT,
        "review": _REVIEW,
        "deliver": _DELIVER,
        **_ENDS,
    },
)
"""A new feature: planned with you, implemented, reviewed in rounds, then delivered as a pull request."""

BUGFIX: Final = Lifecycle(
    name="bugfix",
    initial="implement",
    states={"implement": _IMPLEMENT, "review": _REVIEW, "deliver": _DELIVER, **_ENDS},
)
"""A skeleton second lifecycle: a feature without planning, for a fix whose TASK.md you write yourself."""

LIFECYCLES: Final[Mapping[str, Lifecycle]] = {lifecycle.name: lifecycle for lifecycle in (FEATURE, BUGFIX)}
"""Every lifecycle, by name. A task's STATE.json names one; `foundry task create --lifecycle` chooses it."""

DEFAULT: Final = FEATURE.name
