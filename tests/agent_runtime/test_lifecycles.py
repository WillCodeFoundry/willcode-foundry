"""agent_runtime.task.lifecycles: the lifecycles as written, and the rules a lifecycle is checked against when
it is defined. The expected tables are literals, so a change to a lifecycle shows here."""

import pytest

from agent_runtime.task.lifecycles import (
    BLOCK,
    BUGFIX,
    FEATURE,
    HUMAN,
    LIFECYCLES,
    Event,
    Lifecycle,
    LifecycleInvalid,
    State,
)


def flow(lifecycle: Lifecycle) -> dict[str, tuple[str | None, dict[str, str]]]:
    """Each state's assignee and where each of its events leads."""
    return {
        name: (state.assignee, {event: transition.target for event, transition in state.events.items()})
        for name, state in lifecycle.states.items()
    }


def test_feature_is_planned_implemented_reviewed_and_delivered() -> None:
    assert FEATURE.initial == "plan"
    assert flow(FEATURE) == {
        "plan": ("planner", {"submit": "implement", "block": "blocked"}),
        "implement": ("dev", {"submit": "review", "block": "blocked"}),
        "review": ("reviewer", {"approve": "deliver", "reject": "implement", "block": "blocked"}),
        "deliver": ("dev", {"submit": "done", "block": "blocked"}),
        "blocked": (HUMAN, {}),
        "done": (None, {}),
    }


def test_bugfix_is_feature_without_planning() -> None:
    assert BUGFIX.initial == "implement"
    assert flow(BUGFIX) == {name: value for name, value in flow(FEATURE).items() if name != "plan"}


def test_the_lifecycles_are_found_by_name() -> None:
    assert LIFECYCLES == {"feature": FEATURE, "bugfix": BUGFIX}


def test_every_role_state_says_its_goal_and_when_to_send_each_event() -> None:
    for lifecycle in LIFECYCLES.values():
        for state in lifecycle.states.values():
            if state.assignee not in (None, HUMAN):
                assert state.goal
                assert all(event.when for event in state.events.values())


def role_state(**events: str) -> State:
    return State("dev", "a goal", {name: Event(target, "when") for name, target in events.items()})


@pytest.mark.parametrize(
    ("initial", "states", "problem"),
    [
        ("start", {"work": role_state(block="stuck")}, "its initial state 'start' isn't one of its states"),
        (
            "work",
            {"work": role_state(submit="nowhere", block="stuck"), "stuck": State(HUMAN)},
            "work's submit leads to 'nowhere', which isn't one of its states",
        ),
        (
            "work",
            {"work": role_state(submit="end"), "end": State(None)},
            f"work is a role's state, so it must accept {BLOCK}",
        ),
        (
            "work",
            {"work": role_state(block="end"), "end": State(None)},
            f"work's {BLOCK} must lead to a state assigned to {HUMAN}",
        ),
        (
            "work",
            {"work": role_state(block="stuck"), "stuck": State(HUMAN, events={"x": Event("work", "w")})},
            "stuck is the human's or final, so it accepts no events",
        ),
    ],
    ids=["initial missing", "target missing", "no block", "block not to the human", "human state with events"],
)
def test_a_lifecycle_that_breaks_a_rule_is_refused_when_defined(
    initial: str, states: dict[str, State], problem: str
) -> None:
    with pytest.raises(LifecycleInvalid) as refused:
        Lifecycle(name="bad", initial=initial, states=states)

    assert str(refused.value) == f"lifecycle bad: {problem}"
