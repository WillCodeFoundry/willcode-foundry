"""foundry/task_state.py: task states as the host reads them, against a throwaway repository on disk;
and the `foundry task` subcommands' arguments and output."""

import json
import subprocess
from pathlib import Path

import pytest

from foundry import cli, task_state
from foundry.commands.task import list_lines
from foundry.errors import FoundryError
from foundry.git_clone import GitClone
from foundry.task import NOTES_BRANCH, Task
from foundry.task_state import Lifecycle, TaskState

REPO_ROOT = Path(__file__).parents[1]


def state_json(name: str, *, previous: str | None = None, counts: dict[str, int] | None = None, note: str = "") -> str:
    return json.dumps(
        {
            "lifecycle": "feature",
            "state": name,
            "previous": previous,
            "counts": counts or {},
            "handoff": {"commit": "abc123", "note": note},
        }
    )


def git(env: dict[str, str], *args: str) -> str:
    return subprocess.run(["git", *args], env=env, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def origin_dir(tmp_path: Path, git_env) -> Path:
    """A project whose notes branch holds t0, from before task states, t1 in review and t2 blocked."""
    origin_dir = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    git(git_env, "init", "--quiet", "--bare", "--initial-branch=main", str(origin_dir))
    git(git_env, "init", "--quiet", "--initial-branch=main", str(seed))
    (seed / "README.md").write_text("code\n")
    git(git_env, "-C", str(seed), "add", ".")
    git(git_env, "-C", str(seed), "commit", "--quiet", "-m", "init")
    git(git_env, "-C", str(seed), "switch", "--quiet", "--orphan", NOTES_BRANCH)
    notes = {
        Task("t0").task_file: "# an earlier task\n",
        Task("t1").task_file: "# Task 1\n",
        Task("t1").state_file: state_json("review", previous="ready", note="Start with the parser.\nThen the CLI."),
        Task("t2").task_file: "# Task 2\n",
        Task("t2").state_file: state_json("blocked", previous="review", counts={"review.reject": 3}, note="R7 open."),
    }
    for path, text in notes.items():
        (seed / path).parent.mkdir(parents=True, exist_ok=True)
        (seed / path).write_text(text)
    git(git_env, "-C", str(seed), "add", ".")
    git(git_env, "-C", str(seed), "commit", "--quiet", "-m", "tasks")
    git(git_env, "-C", str(seed), "push", "--quiet", str(origin_dir), "main", NOTES_BRANCH)
    return origin_dir


@pytest.fixture
def notes_clone(tmp_path: Path, origin_dir: Path, git_env) -> GitClone:
    """A scratch clone with the notes branch checked out, as the commands make one."""
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    clone = GitClone.init(str(origin_dir), scratch, git_env)
    clone.check_out(NOTES_BRANCH)
    return clone


FEATURE = task_state.load_lifecycle(REPO_ROOT, "feature")


# --- reading ----------------------------------------------------------------------


def test_every_tasks_state_is_read_from_the_notes_branch(notes_clone) -> None:
    states = task_state.read_all(notes_clone)

    assert list(states) == ["t0", "t1", "t2"]
    assert states["t0"] is None
    assert states["t1"] == TaskState(
        lifecycle="feature",
        state="review",
        previous="ready",
        counts={},
        commit="abc123",
        note="Start with the parser.\nThen the CLI.",
    )
    assert isinstance(states["t2"], TaskState) and states["t2"].counts == {"review.reject": 3}


def test_a_task_the_notes_branch_doesnt_have_is_refused(notes_clone) -> None:
    with pytest.raises(FoundryError, match=r"^there is no task t9: agent-notes has no \.agent/t9/$"):
        task_state.read(notes_clone, Task("t9"))


@pytest.mark.parametrize(
    "text",
    ["not json", "[]", json.dumps({"state": "review"}), state_json("review").replace('"abc123"', "7")],
)
def test_a_malformed_state_is_refused_naming_the_file(text: str) -> None:
    with pytest.raises(FoundryError, match=r"^\.agent/t1/STATE\.json: "):
        TaskState.parse(text, ".agent/t1/STATE.json")


def test_a_state_reads_back_as_bin_task_writes_it() -> None:
    state = TaskState.parse(state_json("changes", previous="review", counts={"review.reject": 1}), "x")

    assert json.loads(state.to_json()) == json.loads(
        state_json("changes", previous="review", counts={"review.reject": 1})
    )
    assert state.to_json().endswith("}\n")


def test_a_lifecycle_names_each_states_assignee() -> None:
    assert (FEATURE.assignee("review"), FEATURE.assignee("blocked"), FEATURE.assignee("done")) == (
        "reviewer",
        "human",
        None,
    )


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("{", "is not valid JSON"),
        ('{"initial": "a"}', "is not a lifecycle: it has no states"),
        ('{"on": [], "states": {"a": {"final": true}}}', "is not a lifecycle: the top level's on isn't an object"),
    ],
)
def test_a_malformed_lifecycle_is_refused(tmp_path: Path, text: str, problem: str) -> None:
    lifecycle_dir = tmp_path / "agent-kit" / "lifecycle"
    lifecycle_dir.mkdir(parents=True)
    (lifecycle_dir / "broken.json").write_text(text)

    with pytest.raises(FoundryError, match=rf"broken\.json {problem}"):
        task_state.load_lifecycle(tmp_path, "broken")


def test_a_missing_lifecycle_is_named(tmp_path: Path) -> None:
    with pytest.raises(FoundryError, match=r"lifecycle 'nope' has no file .*nope\.json"):
        task_state.load_lifecycle(tmp_path, "nope")


# --- the commands -----------------------------------------------------------------


def test_list_shows_each_tasks_state_turn_and_first_line_of_its_note(notes_clone) -> None:
    states = task_state.read_all(notes_clone)

    assert list_lines("tkt-store", states, lambda name: FEATURE) == [
        "tkt-store",
        "  t0  no state",
        "  t1  feature  review  reviewer's turn  Start with the parser.",
        "  t2  feature  blocked  your turn  review.reject 3  R7 open.",
    ]


def test_list_carries_on_past_a_task_it_cant_read(notes_clone, tmp_path) -> None:
    states = task_state.read_all(notes_clone) | {"t3": FoundryError(".agent/t3/STATE.json: not valid JSON")}
    states["t1"] = TaskState.parse(state_json("review").replace('"feature"', '"gone"'), "x")

    def lifecycle(name: str) -> Lifecycle:
        return FEATURE if name == "feature" else task_state.load_lifecycle(tmp_path, name)

    lines = list_lines("tkt-store", states, lifecycle)

    assert lines[2].startswith("  t1  can't be read: lifecycle 'gone' has no file")
    assert lines[3].startswith("  t2  feature  blocked")
    assert lines[4] == "  t3  can't be read: .agent/t3/STATE.json: not valid JSON"


def test_list_of_a_project_without_tasks() -> None:
    assert list_lines("empty", {}, lambda name: FEATURE) == ["empty", "  no tasks"]


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["task", "run", "store", "T1", "dev"], {"project_name": "store", "task_id": "T1", "role_name": "dev"}),
        (["task", "list"], {"project_name": None}),
        (["task", "list", "store"], {"project_name": "store"}),
    ],
)
def test_the_task_subcommands_take_project_and_task_first(argv: list[str], expected: dict[str, object]) -> None:
    args = vars(cli.build_parser().parse_args(argv))

    assert {name: args[name] for name in expected} == expected
