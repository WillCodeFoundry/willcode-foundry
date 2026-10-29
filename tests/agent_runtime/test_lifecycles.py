"""agent_runtime.task.lifecycles: the lifecycles as written, and the rules of a lifecycle's form, which every
lifecycle is held to here. The expected tables are literals, so a change to a lifecycle shows here."""

import pytest

from agent_runtime.task.lifecycles import (
    BLOCK,
    BUGFIX,
    FEATURE,
    LIFECYCLES,
    Lifecycle,
)


def flow(lifecycle: Lifecycle) -> dict[str, tuple[str | None, dict[str, str]]]:
    """Each state's role and where each of its events leads."""
    return {
        name: (state.role, {event: transition.target for event, transition in state.events.items()})
        for name, state in lifecycle.states.items()
    }


def test_feature_is_planned_implemented_reviewed_and_delivered() -> None:
    assert FEATURE.initial == "plan"
    assert flow(FEATURE) == {
        "plan": ("planner", {"submit": "implement", "block": "blocked"}),
        "implement": ("dev", {"submit": "review", "block": "blocked"}),
        "review": ("reviewer", {"approve": "deliver", "reject": "implement", "block": "blocked"}),
        "deliver": ("dev", {"submit": "done", "block": "blocked"}),
        "blocked": (None, {}),
        "done": (None, {}),
    }
    assert (FEATURE.states["blocked"].terminal, FEATURE.states["blocked"].blocked) == (True, True)
    assert (FEATURE.states["done"].terminal, FEATURE.states["done"].blocked) == (True, False)


def test_bugfix_is_feature_without_planning() -> None:
    assert BUGFIX.initial == "implement"
    assert flow(BUGFIX) == {name: value for name, value in flow(FEATURE).items() if name != "plan"}


def test_the_lifecycles_are_found_by_name() -> None:
    assert LIFECYCLES == {"feature": FEATURE, "bugfix": BUGFIX}


@pytest.mark.parametrize("lifecycle", LIFECYCLES.values(), ids=LIFECYCLES)
def test_every_lifecycle_keeps_the_rules_of_its_form(lifecycle: Lifecycle) -> None:
    states = lifecycle.states
    assert lifecycle.initial in states
    for state in states.values():
        assert all(event.target in states for event in state.events.values())
        assert (state.role is None) == state.terminal
        assert not state.blocked or state.terminal
        if state.terminal:
            assert not state.events and not state.goal
        else:
            assert state.goal.strip()
            assert all(event.when.strip() for event in state.events.values())
            assert BLOCK in state.events
            assert set(state.events) != {BLOCK}
            assert states[state.events[BLOCK].target].blocked
