"""agent-kit/bin/task, the agent's command for its task's state, in checkouts made by session-setup.

Each test launches a role on a task in a given state, as a sandbox would be launched. Changes from
outside the sandbox, the human's or another role's, are pushed to origin, as they would be.
"""

import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from foundry.task import NOTES_BRANCH, STATE_FILE, Task

AGENT_KIT_PATH = Path(__file__).parents[2] / "agent-kit"
TASK = Task("T1")
TRAILER = "Task-State: bin/task"


def state(name: str, *, previous: str | None = None, counts: dict[str, int] | None = None, note: str = "") -> str:
    return json.dumps(
        {
            "lifecycle": "feature",
            "state": name,
            "previous": previous,
            "counts": counts or {},
            "handoff": {"commit": "", "note": note},
        }
    )


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def launched(sandbox_checkouts):
    """Launch a role on TASK in a state: (code checkout, notes checkout)."""

    def launch(text: str, *, role: str = "dev", kit_dir: Path | None = None) -> tuple[Path, Path]:
        code, notes = sandbox_checkouts(TASK, notes={STATE_FILE: text}, role=role, kit_dir=kit_dir)
        return Path(code), Path(notes)

    return launch


def task(*args: str) -> subprocess.CompletedProcess[str]:
    """bin/task, as the launched role runs it."""
    return subprocess.run(
        [str(Path(os.environ["AGENT_KIT_DIR"]) / "bin" / "task"), *args],
        env=os.environ,
        capture_output=True,
        text=True,
        check=False,
    )


def pushed_state(notes: Path) -> dict[str, Any]:
    """STATE.json as the notes branch on origin has it."""
    git(notes, "fetch", "-q", "origin", NOTES_BRANCH)
    loaded = json.loads(git(notes, "show", f"origin/{NOTES_BRANCH}:{TASK.state_file}"))
    assert isinstance(loaded, dict)
    return loaded


# --- task EVENT NOTE ------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "start", "event", "end"),
    [
        ("planner", "draft", "submit", "ready"),
        ("dev", "ready", "submit", "review"),
        ("reviewer", "review", "approve", "approved"),
        ("reviewer", "review", "reject", "changes"),
        ("dev", "changes", "submit", "review"),
        ("dev", "approved", "submit", "done"),
        ("dev", "ready", "block", "blocked"),
        ("reviewer", "review", "block", "blocked"),
    ],
)
def test_an_event_moves_the_task_and_is_pushed(launched, role, start, event, end) -> None:
    code, notes = launched(state(start), role=role)

    result = task(event, "Look at the parser first.")

    assert result.returncode == 0, result.stderr
    assert f"{start} → {end}" in result.stdout
    pushed = pushed_state(notes)
    assert (pushed["state"], pushed["previous"]) == (end, start)
    assert pushed["handoff"] == {
        "commit": git(code, "rev-parse", f"origin/{TASK.branch}"),
        "note": "Look at the parser first.",
    }
    message = git(notes, "log", "-1", "--format=%B")
    assert message.startswith(f"{TASK.id}: {start} → {end} ({event}") and TRAILER in message.splitlines()
    assert git(notes, "status", "--porcelain") == ""


def test_the_next_assignee_is_named(launched) -> None:
    launched(state("ready"))

    assert "reviewer's turn" in task("submit", "Ready.").stdout


def test_the_turn_is_origins_whatever_the_notes_checkout_holds(launched, push_task_state) -> None:
    _, notes = launched(state("ready"))
    push_task_state(TASK, state("blocked", previous="ready", note="Moved by the human."))

    result = task("submit", "Done.")

    assert result.returncode == 1 and "waiting for the human" in result.stderr
    assert pushed_state(notes)["state"] == "blocked"


def test_a_role_given_its_turn_back_carries_on_in_the_same_launch(launched, push_task_state) -> None:
    _, notes = launched(state("ready"))
    assert task("block", "Is CSV in scope?").returncode == 0
    push_task_state(TASK, state("ready", previous="blocked", note="Yes, CSV too."))

    result = task("submit", "Done, CSV included.")

    assert result.returncode == 0, result.stderr
    assert (pushed_state(notes)["state"], pushed_state(notes)["previous"]) == ("review", "ready")


def test_an_event_the_state_doesnt_accept_is_refused_listing_those_it_does(launched) -> None:
    launched(state("ready"))

    result = task("approve", "Fine.")

    assert result.returncode == 1
    assert "ready doesn't accept approve" in result.stderr
    assert "\n  submit  when every acceptance criterion is met" in result.stderr
    assert "\n  block   when you need the human" in result.stderr


@pytest.mark.parametrize(
    ("count", "end", "message"),
    [
        (0, "changes", "reject (1 of 3)"),
        (2, "changes", "reject (3 of 3)"),
        (3, "blocked", "reject (limit of 3 reached)"),
    ],
)
def test_reject_counts_and_falls_back_to_blocked(launched, count, end, message) -> None:
    _, notes = launched(state("review", counts={"review.reject": count} if count else {}), role="reviewer")

    result = task("reject", "R2 still open.")

    assert result.returncode == 0, result.stderr
    assert message in result.stdout
    pushed = pushed_state(notes)
    assert pushed["state"] == end
    assert pushed["counts"] == {"review.reject": min(count + 1, 3)}
    if end == "blocked":
        assert "waiting for the human" in result.stdout


def test_a_limited_event_without_a_fallback_is_refused_at_its_limit(launched, tmp_path) -> None:
    kit = tmp_path / "agent-kit"
    shutil.copytree(AGENT_KIT_PATH, kit, symlinks=True)
    (kit / "lifecycle" / "retry.json").write_text(
        json.dumps(
            {
                "initial": "trying",
                "states": {
                    "trying": {
                        "assignee": "dev",
                        "skill": "tdd",
                        "on": {
                            "retry": {"target": "trying", "limit": 2, "when": "it failed"},
                            "finish": {"target": "done", "when": "it worked"},
                        },
                    },
                    "done": {"final": True},
                },
            }
        )
    )
    exhausted = json.loads(state("trying", counts={"trying.retry": 2})) | {"lifecycle": "retry"}
    launched(json.dumps(exhausted), kit_dir=kit)

    result = task("retry", "Again.")

    assert result.returncode == 1
    assert "retry has reached its limit of 2" in result.stderr and "finish" in result.stderr


def test_block_keeps_the_question_and_where_the_task_was(launched) -> None:
    _, notes = launched(state("changes", previous="review", counts={"review.reject": 1}))

    assert task("block", "Should the import accept CSV too?").returncode == 0

    pushed = pushed_state(notes)
    assert (pushed["state"], pushed["previous"], pushed["counts"]) == ("blocked", "changes", {"review.reject": 1})
    assert pushed["handoff"]["note"] == "Should the import accept CSV too?"


def test_block_pushes_unpushed_commits_and_records_them(launched) -> None:
    """A stuck role is the likeliest to have unfinished work. Once the task is handed on it can push no more
    code, so block pushes its commits first, while it is still the role's turn."""
    code, notes = launched(state("ready"))
    (code / "new.txt").write_text("x\n")
    git(code, "add", "new.txt")
    git(code, "commit", "-qm", "feat: new")

    assert task("block", "Should the import accept CSV too?").returncode == 0

    head = git(code, "rev-parse", "HEAD")
    assert git(code, "ls-remote", "origin", TASK.branch).split()[0] == head
    pushed = pushed_state(notes)
    assert (pushed["state"], pushed["handoff"]["commit"]) == ("blocked", head)


def test_block_refuses_uncommitted_code_and_changes_nothing(launched) -> None:
    """Nothing could push uncommitted work once the task is handed on, so it is committed first."""
    code, notes = launched(state("ready"))
    (code / "README.md").write_text("changed\n")

    result = task("block", "Should the import accept CSV too?")

    assert result.returncode == 1
    assert "commit them (unfinished work is fine)" in result.stderr and "block pushes your commits" in result.stderr
    assert pushed_state(notes)["state"] == "ready"


def test_block_that_cant_push_the_commits_changes_nothing(launched, tmp_path) -> None:
    code, notes = launched(state("ready"))
    (code / "new.txt").write_text("x\n")
    git(code, "add", "new.txt")
    git(code, "commit", "-qm", "feat: new")
    hook = tmp_path / "origin.git" / "hooks" / "pre-receive"
    hook.write_text(
        f'#!/bin/sh\nwhile read -r _ _ ref; do [ "$ref" = refs/heads/{TASK.branch} ] && exit 1; done\nexit 0\n'
    )
    hook.chmod(0o755)

    result = task("block", "Should the import accept CSV too?")

    assert result.returncode == 1 and "couldn't push your commits" in result.stderr
    assert pushed_state(notes)["state"] == "ready"


@pytest.mark.parametrize("note", ["", "   "])
def test_a_hand_off_note_is_required(launched, note) -> None:
    launched(state("ready"))

    result = task("submit", note)

    assert result.returncode == 1 and "hand-off note" in result.stderr


def test_unpushed_code_is_refused(launched) -> None:
    code, _ = launched(state("ready"))
    (code / "new.txt").write_text("x\n")
    git(code, "add", "new.txt")
    git(code, "commit", "-qm", "feat: new")

    result = task("submit", "Done.")

    assert result.returncode == 1 and "not pushed" in result.stderr


def test_uncommitted_code_is_refused_but_untracked_files_are_not(launched) -> None:
    code, _ = launched(state("ready"))
    (code / "build.log").write_text("output nobody ignored\n")
    (code / "README.md").write_text("changed\n")

    result = task("submit", "Done.")

    assert result.returncode == 1 and "uncommitted" in result.stderr
    git(code, "checkout", "--", "README.md")
    assert task("submit", "Done.").returncode == 0


def test_a_hand_edit_in_the_notes_checkout_is_refused(launched) -> None:
    _, notes = launched(state("ready"))
    (notes / TASK.state_file).write_text(state("approved"))

    result = task("submit", "Done.")

    assert result.returncode == 1 and "restore it" in result.stderr


@pytest.fixture
def origin_rejecting_pushes(tmp_path):
    """Make origin refuse the next ``n`` pushes, as a push racing another task's would be."""

    def refuse(n: int) -> None:
        counter = tmp_path / "rejections-left"
        counter.write_text(str(n))
        hook = tmp_path / "origin.git" / "hooks" / "pre-receive"
        hook.write_text(
            f'#!/bin/sh\nleft=$(cat "{counter}")\n'
            f'if [ "$left" -gt 0 ]; then echo $((left - 1)) > "{counter}"; echo "busy" >&2; exit 1; fi\n'
        )
        hook.chmod(0o755)

    return refuse


def test_a_rejected_push_is_tried_again(launched, origin_rejecting_pushes) -> None:
    _, notes = launched(state("ready"))
    origin_rejecting_pushes(1)

    result = task("submit", "Done.")

    assert result.returncode == 0, result.stderr
    assert pushed_state(notes)["state"] == "review"


def test_a_push_that_keeps_failing_leaves_nothing_behind(launched, origin_rejecting_pushes) -> None:
    _, notes = launched(state("ready"))
    head = git(notes, "rev-parse", "HEAD")
    origin_rejecting_pushes(3)

    result = task("submit", "Done.")

    assert result.returncode == 1 and "nothing changed" in result.stderr
    assert git(notes, "rev-parse", "HEAD") == head and git(notes, "status", "--porcelain") == ""
    assert pushed_state(notes)["state"] == "ready"
    assert task("submit", "Done.").returncode == 0  # origin takes pushes again


def test_a_task_without_a_state_file_is_explained(sandbox_checkouts) -> None:
    sandbox_checkouts(TASK)

    result = task("submit", "Done.")

    assert result.returncode == 3 and f"has no {STATE_FILE}" in result.stderr


def test_an_unknown_verb_shows_the_usage() -> None:
    result = subprocess.run(
        [str(AGENT_KIT_PATH / "bin" / "task")],
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2 and "usage: task" in result.stderr


# --- task show ------------------------------------------------------------------


def test_show_gives_the_state_the_hand_off_note_and_the_events(launched) -> None:
    launched(
        state("review", previous="changes", counts={"review.reject": 2}, note="R3 fixed in abc123."), role="reviewer"
    )

    result = task("show")

    assert result.returncode == 0, result.stderr
    for expected in (
        "feature lifecycle, in review (your turn)",
        "R3 fixed in abc123.",
        "with the code-review skill",
        "approve  when nothing still open in REVIEW.md needs a change",
        "(2 of 3 used, then blocked)",
        "block    when you need the human",
    ):
        assert expected in result.stdout, expected


@pytest.mark.parametrize(("name", "expected"), [("blocked", "waiting for the human"), ("done", "done")])
def test_show_says_when_its_no_roles_turn(launched, push_task_state, name, expected) -> None:
    launched(state("ready"))
    push_task_state(TASK, state(name, note="Is CSV in scope?"))

    result = task("show")

    assert result.returncode == 0 and expected in result.stdout and "no events" in result.stdout


# --- task check-turn ------------------------------------------------------------


def test_check_turn_passes_on_the_roles_turn(launched) -> None:
    launched(state("ready"))

    assert task("check-turn").returncode == 0


@pytest.mark.parametrize(
    ("name", "message"),
    [("review", "reviewer's turn"), ("blocked", "waiting for the human"), ("done", "is done")],
)
def test_check_turn_names_whose_turn_it_is(launched, push_task_state, name, message) -> None:
    launched(state("ready"))
    push_task_state(TASK, state(name, note="The note."))

    result = task("check-turn")

    assert result.returncode == 1
    assert message in result.stderr and "The note." in result.stderr


def test_check_turn_on_a_task_without_a_state(sandbox_checkouts) -> None:
    sandbox_checkouts(TASK)

    assert task("check-turn").returncode == 3


# --- task check-state ----------------------------------------------------------


def check_state() -> subprocess.CompletedProcess[str]:
    return task("check-state")


def test_check_state_has_nothing_to_check_without_a_launch_record(sandbox_checkouts) -> None:
    """session-setup's task begin writes none for a task created before task states."""
    sandbox_checkouts(TASK)

    assert check_state().returncode == 3


def test_an_unchanged_state_passes(launched) -> None:
    launched(state("ready"))

    assert check_state().returncode == 0


def test_a_transition_made_by_task_passes(launched) -> None:
    launched(state("review", counts={"review.reject": 1}), role="reviewer")
    assert task("reject", "R4.").returncode == 0

    assert check_state().returncode == 0


def test_moves_by_the_human_or_another_role_pass_once_pulled(launched, push_task_state) -> None:
    _, notes = launched(state("ready"))
    assert task("submit", "Done.").returncode == 0
    push_task_state(TASK, state("changes", previous="review"), email="wc-foundry-reviewer@example.com")
    push_task_state(TASK, state("ready", previous="changes"))  # the human, after that
    git(notes, "-c", "commit.gpgsign=false", "pull", "-q", "--rebase", "origin", NOTES_BRANCH)

    assert check_state().returncode == 0


def test_an_uncommitted_hand_edit_is_refused(launched) -> None:
    _, notes = launched(state("ready"))
    (notes / TASK.state_file).write_text(state("review", previous="ready"))

    result = check_state()

    assert result.returncode == 1 and "restore it" in result.stderr


def test_a_hand_edit_committed_as_this_role_is_refused(launched) -> None:
    _, notes = launched(state("ready"))
    (notes / TASK.state_file).write_text(state("approved", previous="ready"))
    git(notes, "commit", "-qam", f"{TASK.id}: approved")
    git(notes, "push", "-q", "origin", NOTES_BRANCH)

    result = check_state()

    assert result.returncode == 1
    assert "in your commit" in result.stderr and "revert --no-edit" in result.stderr


def test_check_state_fails_loudly_without_origin(launched, tmp_path) -> None:
    launched(state("ready"))
    (tmp_path / "origin.git").rename(tmp_path / "unreachable.git")

    result = check_state()

    assert result.returncode == 4 and "couldn't read the task state: origin can't be fetched" in result.stderr


def test_check_state_fails_loudly_with_a_launch_commit_the_clone_lost(launched) -> None:
    launched(state("ready"))
    launch = Path(os.environ["HOME"]) / ".claude" / "launch.json"
    launch.write_text(json.dumps({"notes_base": "0123456789abcdef0123456789abcdef01234567"}))

    result = check_state()

    assert result.returncode == 4 and "couldn't read the task state" in result.stderr


# --- a task state that can't be read ----------------------------------------------


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("{not json", "is not valid JSON"),
        (json.dumps({"state": "ready"}), "is not a task state"),
        (state("ready", counts={"review.reject": -1}), "is not a task state"),
        (state("ready").replace('"feature"', '"nowhere"'), "lifecycle 'nowhere' has no file"),
        (state("nowhere"), "which its lifecycle doesn't have"),
    ],
)
@pytest.mark.parametrize("verb", [["show"], ["check-turn"], ["check-state"], ["submit", "Done."]])
def test_a_task_state_that_cant_be_read_exits_4(launched, push_task_state, text, problem, verb) -> None:
    launched(state("ready"))
    push_task_state(TASK, text)

    result = task(*verb)

    assert result.returncode == 4
    assert "couldn't read the task state" in result.stderr and problem in result.stderr


FEATURE_PATH = AGENT_KIT_PATH / "lifecycle" / "feature.json"


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (lambda lifecycle: lifecycle | {"on": []}, "the top level's on isn't an object"),
        (lambda lifecycle: lifecycle | {"states": {}}, "it has no states"),
        (lambda lifecycle: lifecycle | {"on": {"block": {"target": "blocked"}}}, "block needs a target and a when"),
        (
            lambda lifecycle: lifecycle | {"on": {"block": {"target": "nowhere", "when": "x"}}},
            "block has a target that isn't one of its states",
        ),
        (
            lambda lifecycle: lifecycle | {"on": {"block": {"target": "blocked", "when": "x", "limit": 0}}},
            "block has a limit that isn't a whole number from 1",
        ),
    ],
)
@pytest.mark.parametrize("verb", [["show"], ["check-turn"], ["block", "Q?"]])
def test_a_lifecycle_that_isnt_one_exits_4(launched, tmp_path, change, problem, verb) -> None:
    """Never a traceback's exit 1, which the hooks would take for someone else's turn."""
    kit = tmp_path / "agent-kit"
    shutil.copytree(AGENT_KIT_PATH, kit, symlinks=True)
    launched(state("ready"), kit_dir=kit)
    (kit / "lifecycle" / "feature.json").write_text(json.dumps(change(json.loads(FEATURE_PATH.read_text()))))

    result = task(*verb)

    assert result.returncode == 4
    assert "couldn't read the task state" in result.stderr and problem in result.stderr


def load_bin_task() -> Any:
    loader = importlib.machinery.SourceFileLoader("bin_task", str(AGENT_KIT_PATH / "bin" / "task"))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("bin_task", loader))  # type: ignore[arg-type]
    loader.exec_module(module)
    return module


def test_an_unexpected_failure_exits_4_with_its_traceback(monkeypatch, capsys) -> None:
    kit = load_bin_task()

    def broken() -> None:
        raise AttributeError("a bug")

    monkeypatch.setattr(kit, "show", broken)

    assert kit.main(["show"]) == 4
    error = capsys.readouterr().err
    assert "AttributeError: a bug" in error and "failed unexpectedly" in error
