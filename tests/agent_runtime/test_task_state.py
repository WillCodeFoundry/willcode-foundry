"""agent_runtime.task.state: reading and writing STATE.json, applying events, moves by hand, and the transition
rule."""

import pytest

from agent_runtime.task.lifecycles import BUGFIX, FEATURE
from agent_runtime.task.state import (
    TaskState,
    TaskStateRefused,
    commit_subject,
    require_legal_transition,
)

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


# --- events -------------------------------------------------------------------


def test_an_event_moves_the_task_and_leaves_the_note() -> None:
    after = in_state("review", note="ready").after("reject", "  R3 is open.  ")

    assert after == in_state("implement", note="R3 is open.")
    assert after.assignee == "dev"


def test_block_hands_any_role_state_to_the_human() -> None:
    after = in_state("deliver").after("block", "Which base branch?")

    assert (after.state, after.assignee) == ("blocked", "human")


@pytest.mark.parametrize(("state", "assignee"), [("blocked", "the human"), ("done", "no one")])
def test_a_state_without_events_refuses_any_and_says_to_stop(state: str, assignee: str) -> None:
    assert refusal(lambda: in_state(state).after("submit", "note")) == (
        f"{state} accepts no events. The task is assigned to {assignee}, so stop here."
    )


def test_an_event_the_state_doesnt_accept_is_refused_listing_those_it_does() -> None:
    assert refusal(lambda: in_state("implement").after("approve", "note")) == (
        "implement doesn't accept 'approve'. Send one of submit, block (see \"$AGENT_KIT_DIR/bin/task\" show)."
    )


@pytest.mark.parametrize("note", ["", "  \n"])
def test_an_event_without_a_hand_off_note_is_refused(note: str) -> None:
    assert "Give a hand-off note" in refusal(lambda: in_state("implement").after("submit", note))


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


# --- the transition rule ------------------------------------------------------


@pytest.mark.parametrize(
    ("event", "note"), [("approve", "LGTM"), ("reject", "R3 is open."), ("block", "Is R4 in scope?")]
)
def test_what_an_event_does_is_a_legal_transition(event: str, note: str) -> None:
    review = in_state("review", note="Ready.")

    require_legal_transition(review, review.after(event, note), "reviewer")


def test_a_note_with_surrounding_whitespace_is_legal() -> None:
    require_legal_transition(in_state("review"), in_state("deliver", note="  LGTM \n"), "reviewer")


@pytest.mark.parametrize(
    ("new", "role", "refusal_given"),
    [
        (
            in_state("deliver", note="LGTM"),
            "dev",
            "The task is assigned to the reviewer, not the dev. It is in review.",
        ),
        (
            TaskState(lifecycle=BUGFIX, state="deliver", note="LGTM"),
            "reviewer",
            "The lifecycle can't change. It is feature.",
        ),
        (
            in_state("done", note="LGTM"),
            "reviewer",
            "review can't go to done. Its events lead to blocked, deliver, implement.",
        ),
        (
            in_state("deliver", note=" \n"),
            "reviewer",
            "Give a hand-off note. Say what the next assignee should read first.",
        ),
    ],
    ids=["another role", "another lifecycle", "not a target", "no note"],
)
def test_every_other_change_is_refused_saying_why(new: TaskState, role: str, refusal_given: str) -> None:
    assert refusal(lambda: require_legal_transition(in_state("review"), new, role)) == refusal_given
