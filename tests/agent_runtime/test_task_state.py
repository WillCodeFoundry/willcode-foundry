"""agent_runtime.task.state: reading and writing STATE.json, applying events, moves by hand, and which changes
are legal transitions."""

import dataclasses
import json

import pytest

from agent_runtime.task.lifecycles import BUGFIX, FEATURE
from agent_runtime.task.state import TaskState, TaskStateRefused, legal_change

WHERE = ".agent/t1/STATE.json"


def in_state(state: str, *, previous: str | None = None, note: str = "") -> TaskState:
    return TaskState(lifecycle=FEATURE, state=state, previous=previous, note=note)


def refusal(call) -> str:
    with pytest.raises(TaskStateRefused) as refused:
        call()
    return str(refused.value)


# --- STATE.json ---------------------------------------------------------------


def test_a_new_task_is_in_its_lifecycles_initial_state() -> None:
    assert TaskState.new(FEATURE).to_json() == (
        '{\n  "lifecycle": "feature",\n  "state": "plan",\n  "previous": null,\n  "note": ""\n}\n'
    )
    assert TaskState.new(BUGFIX).state == "implement"


def test_a_task_state_reads_back_as_written() -> None:
    written = in_state("review", previous="implement", note="Start with parser.py — and the tests.")

    assert TaskState.parse(written.to_json(), WHERE) == written


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("{", f"{WHERE} is not valid JSON"),
        ("[]", f"{WHERE} is not a task state: it must hold exactly lifecycle, state, previous, note"),
        (
            '{"lifecycle": "feature", "state": "plan", "previous": null, "note": "", "counts": {}}',
            f"{WHERE} is not a task state",
        ),
        (
            '{"lifecycle": "epic", "state": "plan", "previous": null, "note": ""}',
            f"{WHERE} names no known lifecycle: 'epic'",
        ),
        (
            '{"lifecycle": "bugfix", "state": "plan", "previous": null, "note": ""}',
            f"{WHERE}: state 'plan' is not a state of bugfix",
        ),
        (
            '{"lifecycle": "feature", "state": "plan", "previous": "draft", "note": ""}',
            f"{WHERE}: previous 'draft' is not a state of feature",
        ),
        ('{"lifecycle": "feature", "state": "plan", "previous": null, "note": 3}', f"{WHERE}: note must be text"),
    ],
    ids=["not JSON", "not an object", "an extra key", "unknown lifecycle", "unknown state", "unknown previous", "note"],
)
def test_anything_but_a_task_state_is_refused_naming_the_file(text: str, message: str) -> None:
    assert refusal(lambda: TaskState.parse(text, WHERE)).startswith(message)


# --- events -------------------------------------------------------------------


def test_an_event_moves_the_task_and_records_where_it_came_from() -> None:
    after = in_state("review", previous="implement", note="ready").after("reject", "reviewer", "  R3 is open.  ")

    assert after == in_state("implement", previous="review", note="R3 is open.")
    assert after.turn == "dev"


def test_block_hands_any_role_state_to_the_human() -> None:
    after = in_state("deliver").after("block", "dev", "Which base branch?")

    assert (after.state, after.turn) == ("blocked", "human")


@pytest.mark.parametrize(
    ("state", "role", "message"),
    [
        ("review", "dev", "it is the reviewer's turn, not the dev's: the task is in review. Stop here"),
        ("blocked", "dev", "it is the human's turn, not the dev's: the task is in blocked. Stop here"),
        ("done", "dev", "the task is done: it is no one's turn. Stop here"),
    ],
)
def test_an_event_off_the_roles_turn_is_refused(state: str, role: str, message: str) -> None:
    assert refusal(lambda: in_state(state).after("submit", role, "note")).startswith(message)


def test_an_event_the_state_doesnt_accept_is_refused_listing_those_it_does() -> None:
    assert refusal(lambda: in_state("implement").after("approve", "dev", "note")) == (
        "implement doesn't accept 'approve': send one of submit, block (see \"$AGENT_KIT_DIR/bin/task\" show)"
    )


@pytest.mark.parametrize("note", ["", "  \n"])
def test_an_event_without_a_hand_off_note_is_refused(note: str) -> None:
    assert "give a hand-off note" in refusal(lambda: in_state("implement").after("submit", "dev", note))


# --- moves by hand ------------------------------------------------------------


@pytest.mark.parametrize("to", ["plan", "done", "blocked"])
def test_a_move_by_hand_goes_to_any_state(to: str) -> None:
    assert in_state("blocked", previous="review").moved(to, "Answered in TASK.md") == in_state(
        to, previous="blocked", note="Answered in TASK.md"
    )


def test_a_move_to_a_state_the_lifecycle_lacks_is_refused() -> None:
    assert refusal(lambda: in_state("blocked").moved("draft", "x")) == (
        "feature has no state 'draft'; its states: plan, implement, review, deliver, blocked, done"
    )


def test_a_move_without_a_note_is_refused() -> None:
    assert "give a hand-off note" in refusal(lambda: in_state("blocked").moved("review", " "))


# --- legal changes ------------------------------------------------------------


def test_what_an_event_does_is_a_legal_change() -> None:
    old = in_state("review", previous="implement", note="ready")

    assert legal_change(old, old.after("approve", "reviewer", "LGTM"), "reviewer") is None


@pytest.mark.parametrize(
    ("new", "role", "reason"),
    [
        (
            dataclasses.replace(in_state("implement", previous="review", note="n"), lifecycle=BUGFIX),
            "reviewer",
            "the lifecycle changed from feature to bugfix",
        ),
        (in_state("deliver", previous="review", note="n"), "dev", "it is the reviewer's turn, not the dev's"),
        (in_state("done", previous="review", note="n"), "reviewer", "review can't go to done: its events lead to"),
        (in_state("deliver", previous="plan", note="n"), "reviewer", "previous must be review"),
        (in_state("deliver", previous="review", note=" "), "reviewer", "the hand-off note is empty"),
    ],
    ids=["lifecycle", "not the role's turn", "not a target", "previous", "no note"],
)
def test_every_other_change_is_illegal_and_says_why(new: TaskState, role: str, reason: str) -> None:
    reason_given = legal_change(in_state("review", previous="implement", note="ready"), new, role)

    assert reason_given is not None and reason_given.startswith(reason)


def test_to_json_is_plain_json() -> None:
    assert json.loads(in_state("plan").to_json()) == {
        "lifecycle": "feature",
        "state": "plan",
        "previous": None,
        "note": "",
    }
