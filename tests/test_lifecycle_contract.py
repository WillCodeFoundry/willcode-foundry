"""Every lifecycle in agent-kit/lifecycle/ has the format agent-kit/bin/task reads, names only roles the
foundry has, and keeps the rules that hold across lifecycles; and a new task's STATE.json starts in one.

Read as JSON here, without importing bin/task: this holds the files to the format, and bin/task's own
tests hold it to the same format from the other side."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from foundry import config, paths
from foundry.task import STATE_FILE

REPO_ROOT = Path(__file__).parents[1]
LIFECYCLE_DIR = paths.lifecycle_dir(REPO_ROOT)
LIFECYCLES = sorted(LIFECYCLE_DIR.glob("*.json"))
TEMPLATE_STATE = paths.task_template_dir(REPO_ROOT) / STATE_FILE

# bin/task's own verbs, which an event's name would shadow.
TASK_VERBS = {"show", "begin", "check-turn", "check-state"}
HUMAN = "human"


def load(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text())
    assert isinstance(loaded, dict), f"{path.name}: not a JSON object"
    return loaded


def transitions(state: dict[str, Any]) -> dict[str, Any]:
    on = state.get("on", {})
    assert isinstance(on, dict)
    return on


def targets(transition: dict[str, Any]) -> list[str]:
    """The states a transition can lead to: its target, and its fallback if it has one."""
    return [transition["target"], *([transition["fallback"]] if "fallback" in transition else [])]


def events_of(lifecycle: dict[str, Any], name: str) -> dict[str, Any]:
    """The events a state accepts: its own and, for a role's state, the lifecycle's top-level ones."""
    state = lifecycle["states"][name]
    if state.get("assignee") in (None, HUMAN):
        return {}
    return {**lifecycle.get("on", {}), **transitions(state)}


def reachable(lifecycle: dict[str, Any]) -> set[str]:
    """The states events can lead to from initial."""
    seen = {lifecycle["initial"]}
    pending = [lifecycle["initial"]]
    while pending:
        name = pending.pop()
        for transition in events_of(lifecycle, name).values():
            for target in targets(transition):
                if target not in seen:
                    seen.add(target)
                    pending.append(target)
    return seen


def test_there_is_a_feature_lifecycle() -> None:
    assert LIFECYCLE_DIR / "feature.json" in LIFECYCLES


@pytest.mark.parametrize("path", LIFECYCLES, ids=lambda path: path.stem)
def test_the_format_is_the_one_bin_task_reads(path: Path) -> None:
    lifecycle = load(path)
    assert re.fullmatch(r"[a-z0-9][a-z0-9-]*", path.stem)
    assert set(lifecycle) <= {"initial", "on", "states"} and {"initial", "states"} <= set(lifecycle)
    assert isinstance(lifecycle["states"], dict) and lifecycle["states"]
    for name, state in lifecycle["states"].items():
        assert isinstance(state, dict), name
        if state.get("final") is True:
            assert state == {"final": True}, f"{name}: a final state has nothing else"
        elif state.get("assignee") == HUMAN:
            assert state == {"assignee": HUMAN}, f"{name}: a human state has no skill and accepts no events"
        else:
            assert set(state) == {"assignee", "skill", "on"}, f"{name}: a role's state has assignee, skill and on"
            assert isinstance(state["skill"], str), name
    for on in [lifecycle.get("on", {}), *(transitions(state) for state in lifecycle["states"].values())]:
        for event, transition in on.items():
            assert re.fullmatch(r"[a-z][a-z-]*", event), event
            assert isinstance(transition, dict), f"{event}: a transition is an object"
            assert set(transition) <= {"target", "when", "limit", "fallback"}, event
            assert {"target", "when"} <= set(transition), f"{event}: every event says its target and when to send it"
            assert all(isinstance(transition[key], str) for key in ("target", "when", "fallback") if key in transition)
            assert "fallback" not in transition or "limit" in transition, f"{event}: a fallback needs a limit"
            if "limit" in transition:
                assert type(transition["limit"]) is int and transition["limit"] >= 1, event  # not bool


@pytest.mark.parametrize("path", LIFECYCLES, ids=lambda path: path.stem)
def test_every_role_has_the_skill_its_states_name(path: Path) -> None:
    missing = [
        f"{name}: {state['assignee']} has no {state['skill']} skill"
        for name, state in load(path)["states"].items()
        if "skill" in state and not (paths.role_dir(REPO_ROOT, state["assignee"]) / "skills" / state["skill"]).is_dir()
    ]
    assert missing == []


@pytest.mark.parametrize("path", LIFECYCLES, ids=lambda path: path.stem)
def test_block_takes_any_role_to_the_human(path: Path) -> None:
    """AGENTS.md tells every role to block when it needs the human, whatever the lifecycle and the state.

    Whether a state overrides block or not, block must lead to a human state, wherever its limit leaves it.
    """
    lifecycle = load(path)
    states = lifecycle["states"]
    roles_states = [name for name, state in states.items() if state.get("assignee") not in (None, HUMAN)]
    wrong = [
        f"{name}: block can lead to {target}"
        for name in roles_states
        for target in targets(events_of(lifecycle, name).get("block", {"target": "(nothing)"}))
        if states.get(target) != {"assignee": HUMAN}
    ]
    assert wrong == []


@pytest.mark.parametrize("path", LIFECYCLES, ids=lambda path: path.stem)
def test_every_state_it_names_exists(path: Path) -> None:
    lifecycle = load(path)
    states = lifecycle["states"]
    named = [lifecycle["initial"]] + [
        target
        for on in [lifecycle.get("on", {}), *(transitions(state) for state in states.values())]
        for transition in on.values()
        for target in targets(transition)
    ]
    assert [name for name in named if name not in states] == []


@pytest.mark.parametrize("path", LIFECYCLES, ids=lambda path: path.stem)
def test_every_assignee_is_a_role_or_the_human(path: Path) -> None:
    roles = set(config.load(REPO_ROOT).roles)
    assignees = {state["assignee"] for state in load(path)["states"].values() if "assignee" in state}
    assert assignees - roles - {HUMAN} == set()


@pytest.mark.parametrize("path", LIFECYCLES, ids=lambda path: path.stem)
def test_no_event_is_named_like_one_of_bin_tasks_verbs(path: Path) -> None:
    lifecycle = load(path)
    events = {event for name in lifecycle["states"] for event in events_of(lifecycle, name)}
    assert events & TASK_VERBS == set()


@pytest.mark.parametrize("path", LIFECYCLES, ids=lambda path: path.stem)
def test_events_reach_every_state_but_the_final_ones(path: Path) -> None:
    lifecycle = load(path)
    unreached = set(lifecycle["states"]) - reachable(lifecycle)
    assert {name for name in unreached if lifecycle["states"][name].get("final") is not True} == set()


# Lines that name a state or event's word in its everyday sense, not the state or event.
EVERYDAY_USES = {
    "agent-kit/skills/git-conventions/SKILL.md": [
        "- `fix bug`, `wip`, `update`, `changes`: say which bug, which update."
    ],
}


def test_no_instructions_name_a_lifecycles_states_or_events() -> None:
    """What a state asks of its assignee lives in its lifecycle (its skill, and each event's when), so a new
    lifecycle needs no edits to AGENTS.md, a ROLE.md or a skill. block is the one event the kit defines for
    every lifecycle (test_block_takes_any_role_to_the_human), so instructions may name it.

    It catches the ways instructions mark a name (backticks, bold, "task is in", a bin/task call), not a
    state named in plain prose: words like "ready" or "done" are too common to tell apart. Review catches those."""
    states: set[str] = set()
    events: set[str] = set()
    for path in LIFECYCLES:
        lifecycle = load(path)
        states |= set(lifecycle["states"])
        events |= {event for name in lifecycle["states"] for event in events_of(lifecycle, name)}
    events.discard("block")
    named = "|".join(map(re.escape, sorted(states | events)))
    pattern = re.compile(
        rf"`(?:{named})`|\*\*(?:{named}):?\*\*|task is in (?:{named})\b"
        rf"|bin/task\"? (?:{'|'.join(map(re.escape, sorted(events)))})\b"
    )
    found = [
        f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()}"
        for path in sorted((REPO_ROOT / "agent-kit").rglob("*.md"))
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if pattern.search(line) and line.strip() not in EVERYDAY_USES.get(str(path.relative_to(REPO_ROOT)), [])
    ]
    assert found == []


def test_a_new_task_starts_in_its_lifecycles_initial_state() -> None:
    state = load(TEMPLATE_STATE)
    assert state == {
        "lifecycle": "feature",
        "state": load(LIFECYCLE_DIR / "feature.json")["initial"],
        "previous": None,
        "counts": {},
        "handoff": {"commit": "", "note": ""},
    }
