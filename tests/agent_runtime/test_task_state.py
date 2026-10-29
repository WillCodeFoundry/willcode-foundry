"""agent_runtime.task.state: reading and writing STATE.json, applying events, moves by hand, and the transition
rule."""

import pytest

from agent_runtime.task.lifecycles import BUGFIX, FEATURE
from agent_runtime.task.state import TaskState, TaskStateRefused, commit_subject

WHERE = ".agent/t1/STATE.json"


def in_state(state: str, *, note: str = "") -> TaskState:
    return TaskState(lifecycle=FEATURE, state=state, note=note)


def refusal(call) -> str:
    with pytest.raises(TaskStateRefused) as refused:
        call()
    return str(refused.value)


# --- STATE.json ---------------------------------------------------------------


def test_a_new_task_is_in_its_lifecycles_initial_state() -> None:
    assert TaskState.new(FEATURE).to_json() == ('{\n  "lifecycle": "feature",\n  "state": "plan",\n  "note": ""\n}\n')
    assert TaskState.new(BUGFIX).state == "implement"


def test_a_task_state_reads_back_as_written() -> None:
    written = in_state("review", note="Start with parser.py — and the tests.")

    assert TaskState.parse(written.to_json(), WHERE) == written


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("{", f"{WHERE} is not valid JSON"),
        ("[]", f"{WHERE} is not a task state. It must hold exactly lifecycle, state, note."),
        (
            '{"lifecycle": "feature", "state": "plan", "note": "", "counts": {}}',
            f"{WHERE} is not a task state",
        ),
        (
            '{"lifecycle": "epic", "state": "plan", "note": ""}',
            f"{WHERE} names no known lifecycle, 'epic'.",
        ),
        (
            '{"lifecycle": "bugfix", "state": "plan", "note": ""}',
            f"{WHERE}: state 'plan' is not a state of bugfix",
        ),
        ('{"lifecycle": "feature", "state": "plan", "note": 3}', f"{WHERE}: note must be text"),
    ],
    ids=["not JSON", "not an object", "an extra key", "unknown lifecycle", "unknown state", "note"],
)
def test_anything_but_a_task_state_is_refused_naming_the_file(text: str, message: str) -> None:
    assert refusal(lambda: TaskState.parse(text, WHERE)).startswith(message)


# --- events: the transition rule ----------------------------------------------


def test_an_event_moves_the_task_and_leaves_the_note() -> None:
    next_state = in_state("review", note="ready").after("reject", "  R3 is open.  ", "reviewer")

    assert next_state == in_state("implement", note="R3 is open.")
    assert next_state.role == "dev"


def test_block_moves_any_role_state_to_blocked() -> None:
    next_state = in_state("deliver").after("block", "Which base branch?", "dev")

    assert (next_state.state, next_state.role, next_state.blocked) == ("blocked", None, True)


@pytest.mark.parametrize(
    ("state", "event", "refusal_given"),
    [
        ("review", "approve", "The dev can't send events in review. It is assigned to the reviewer."),
        ("review", "submit", "The dev can't send events in review. It is assigned to the reviewer."),
        ("blocked", "submit", "The dev can't send events in blocked. It waits for a human."),
        ("done", "submit", "The dev can't send events in done. No role works on it."),
    ],
    ids=["another role's event", "an event its state lacks", "blocked", "done"],
)
def test_an_event_off_the_roles_turn_is_refused_whatever_the_event(state: str, event: str, refusal_given: str) -> None:
    assert refusal(lambda: in_state(state).after(event, "note", "dev")) == refusal_given


def test_an_event_the_state_doesnt_accept_is_refused_listing_those_it_does() -> None:
    assert refusal(lambda: in_state("implement").after("approve", "note", "dev")) == (
        "implement doesn't accept 'approve'. Send one of submit, block (see \"$AGENT_KIT_DIR/bin/task\" show)."
    )


@pytest.mark.parametrize("note", ["", "  \n"])
def test_an_event_without_a_hand_off_note_is_refused(note: str) -> None:
    assert "Give a hand-off note" in refusal(lambda: in_state("implement").after("submit", note, "dev"))


@pytest.mark.parametrize(("to", "event"), [("deliver", "approve"), ("implement", "reject"), ("blocked", "block")])
def test_the_event_to_a_state_is_the_one_leading_there(to: str, event: str) -> None:
    assert in_state("review").event_to(to) == event


@pytest.mark.parametrize(
    ("state", "to", "refusal_given"),
    [
        ("review", "done", "review can't go to done. Its events lead to blocked, deliver, implement."),
        (
            "blocked",
            "implement",
            "blocked can't go to implement. No event leaves it. It waits for a human.",
        ),
    ],
)
def test_no_event_to_a_state_is_refused_saying_where_the_events_lead(state: str, to: str, refusal_given: str) -> None:
    assert refusal(lambda: in_state(state).event_to(to)) == refusal_given


def test_a_commit_subject_says_where_from_where_to_and_why() -> None:
    assert commit_subject("t1", "implement", "review", "submit") == "t1: implement → review (submit)"


# --- moves by hand ------------------------------------------------------------


@pytest.mark.parametrize("to", ["plan", "done", "blocked"])
def test_a_move_by_hand_goes_to_any_state(to: str) -> None:
    assert in_state("blocked").moved(to, "Answered in TASK.md") == in_state(to, note="Answered in TASK.md")


def test_a_move_to_a_state_the_lifecycle_lacks_is_refused() -> None:
    assert refusal(lambda: in_state("blocked").moved("draft", "x")) == (
        "feature has no state 'draft'. Its states are plan, implement, review, deliver, blocked, done."
    )


def test_a_move_without_a_note_is_refused() -> None:
    assert "Give a hand-off note" in refusal(lambda: in_state("blocked").moved("review", " "))
