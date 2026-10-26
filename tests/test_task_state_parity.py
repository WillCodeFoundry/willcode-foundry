"""The host's task_state and the kit's bin/task read task states and lifecycles alike.

The kit runs in the sandbox without foundry's package, so each side has its own code for the same files.
These tests run the same inputs through both, so the two can't drift apart unnoticed: which STATE.json
they accept, which lifecycles they refuse and why, which counts a lifecycle keeps (what foundry task move
--reset can clear), whose turn each state is, and how a transition's commit is summed up.
"""

import importlib.machinery
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from foundry import paths, task_state
from foundry.errors import FoundryError

REPO_ROOT = Path(__file__).parents[1]


def load_bin_task() -> ModuleType:
    path = paths.agent_kit_dir(REPO_ROOT) / "bin" / "task"
    loader = importlib.machinery.SourceFileLoader("bin_task", str(path))
    spec = importlib.util.spec_from_loader("bin_task", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


kit = load_bin_task()


def state(**changes: Any) -> dict[str, Any]:
    return {
        "lifecycle": "feature",
        "state": "review",
        "previous": "ready",
        "counts": {"review.reject": 1},
        "handoff": {"commit": "abc123", "note": "R1 fixed."},
        **changes,
    }


@pytest.mark.parametrize(
    "text",
    [
        json.dumps(state()),
        json.dumps(state(previous=None, counts={})),
        json.dumps(state(counts={"review.reject": 0})),
        json.dumps(state(counts={"review.reject": -1})),
        json.dumps(state(counts={"review.reject": True})),
        json.dumps(state(counts={"review.reject": 1.0})),
        json.dumps(state(counts=[])),
        json.dumps(state(previous=3)),
        json.dumps(state(handoff={"commit": "abc123"})),
        json.dumps(state(handoff={"commit": "abc123", "note": None})),
        json.dumps({**state(), "extra": 1}),
        json.dumps({key: value for key, value in state().items() if key != "previous"}),
        json.dumps({**{key: value for key, value in state().items() if key != "handoff"}, "data": state()["handoff"]}),
        "[]",
        "{not json",
    ],
)
def test_both_accept_the_same_task_states(text: str) -> None:
    try:
        host = task_state.TaskState.parse(text, "STATE.json")
    except FoundryError:
        host = None
    try:
        ours = kit.parse_state(text, "STATE.json")
    except kit.Unreadable:
        ours = None

    assert (host is None) == (ours is None)
    if host is not None:
        assert json.loads(host.to_json()) == ours


LIFECYCLES: dict[str, dict[str, Any]] = {
    **{path.stem: json.loads(path.read_text()) for path in sorted(paths.lifecycle_dir(REPO_ROOT).glob("*.json"))},
    # A limited top-level event, which one state redefines without a limit.
    "top-level-limit": {
        "initial": "work",
        "on": {"block": {"target": "stuck", "when": "x", "limit": 2, "fallback": "stuck"}},
        "states": {
            "work": {"assignee": "dev", "skill": "tdd", "on": {"submit": {"target": "check", "when": "x"}}},
            "check": {
                "assignee": "reviewer",
                "skill": "code-review",
                "on": {"block": {"target": "stuck", "when": "x"}, "approve": {"target": "end", "when": "x"}},
            },
            "stuck": {"assignee": "human"},
            "end": {"final": True},
        },
    },
}


@pytest.fixture(params=sorted(LIFECYCLES))
def lifecycle(request, tmp_path) -> tuple[dict[str, Any], task_state.Lifecycle]:
    """A lifecycle as the kit reads it, and as the host loads it from a foundry's agent-kit."""
    raw = LIFECYCLES[request.param]
    path = paths.lifecycle_path(tmp_path, request.param)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(raw))
    return raw, task_state.load_lifecycle(tmp_path, request.param)


def test_both_keep_the_same_counts(lifecycle) -> None:
    """The counts bin/task's own apply writes, applying each limited event once in each state that accepts it."""
    raw, host = lifecycle
    ours = set()
    for name in raw["states"]:
        record = {"lifecycle": "x", "state": name, "previous": None, "counts": {}, "handoff": {}}
        for event, transition in kit.accepted(raw, name).items():
            if "limit" in transition:
                ours |= set(kit.apply(raw, record, event).counts)

    assert sorted(host.limited_events()) == sorted(ours)


def test_both_sum_up_a_transition_alike() -> None:
    assert task_state.transition_message("t1", "blocked", "changes", "moved by hand") == kit.transition_message(
        "t1", "blocked", "changes", "moved by hand"
    )


def test_both_give_each_state_to_the_same_assignee(lifecycle) -> None:
    raw, host = lifecycle

    assert {name: host.assignee(name) for name in raw["states"]} == {
        name: kit.assignee(raw, name) for name in raw["states"]
    }


FEATURE = json.loads((paths.lifecycle_dir(REPO_ROOT) / "feature.json").read_text())


@pytest.mark.parametrize(
    "raw",
    [
        FEATURE,
        [],
        {"initial": "a"},
        {"states": {}},
        FEATURE | {"on": []},
        FEATURE | {"states": {**FEATURE["states"], "ready": "dev"}},
        FEATURE | {"states": {**FEATURE["states"], "ready": {"assignee": "dev", "skill": "tdd", "on": []}}},
        FEATURE | {"on": {"block": "blocked"}},
        FEATURE | {"on": {"block": {"target": "blocked"}}},
        FEATURE | {"on": {"block": {"target": "nowhere", "when": "x"}}},
        FEATURE | {"on": {"block": {"target": "blocked", "when": "x", "limit": 2, "fallback": ["done"]}}},
        FEATURE | {"on": {"block": {"target": "blocked", "when": "x", "limit": 0}}},
        FEATURE | {"on": {"block": {"target": "blocked", "when": "x", "limit": True}}},
    ],
)
def test_both_refuse_the_same_lifecycles_for_the_same_reason(raw: Any, tmp_path) -> None:
    """The kit refuses with exit 4 (bin/task's own tests); foundry task list, next and move with an error."""
    path = paths.lifecycle_path(tmp_path, "candidate")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(raw))
    try:
        task_state.load_lifecycle(tmp_path, "candidate")
        host = None
    except FoundryError as error:
        host = str(error).removeprefix(f"{path} is not a lifecycle: ")

    assert host == kit.lifecycle_problem(raw)
