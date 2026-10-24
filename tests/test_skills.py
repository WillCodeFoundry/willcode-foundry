"""foundry/skills.py against a throwaway source repository on disk, and the `foundry skills update` command's
report and arguments."""

import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest
import yaml

from foundry import cli, skills
from foundry.commands.skills import report
from foundry.errors import FoundryError
from foundry.git_clone import GitClone

TDD_SKILL = textwrap.dedent("""\
    ---
    name: tdd
    description: Use when the user wants tests first.
    ---

    # TDD

    Confirm the seams with the user.
    """)

PR_SKILL = textwrap.dedent("""\
    ---
    name: pr
    description: "Use when writing a PR body."
    metadata:
      credits:
        author: Dex Horthy
    ---

    Use this template.
    """)

# Rewrites tdd's description and its line about seams; paths are relative to the skill's folder.
TDD_PATCH = "".join(
    line + "\n"
    for line in [
        "diff --git a/SKILL.md b/SKILL.md",
        "--- a/SKILL.md",
        "+++ b/SKILL.md",
        "@@ -1,8 +1,8 @@",
        " ---",
        " name: tdd",
        "-description: Use when the user wants tests first.",
        "+description: Use when a role writes code test-first.",
        " ---",
        " ",
        " # TDD",
        " ",
        "-Confirm the seams with the user.",
        "+Take the seams from TASK.md.",
    ]
)


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def write_files(root: Path, files: dict[str, str]) -> None:
    for path, text in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text)


def files_under(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): path.read_text() for path in sorted(root.rglob("*")) if path.is_file()}


def frontmatter(skill_md: str) -> dict[str, object]:
    match = re.match(r"---\n(.*?)\n---\n", skill_md, re.DOTALL)
    assert match, f"no frontmatter in:\n{skill_md}"
    loaded = yaml.safe_load(match[1])
    assert isinstance(loaded, dict)
    return loaded


def body(skill_md: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n", "", skill_md, flags=re.DOTALL)


UPSTREAM = {
    "LICENSE": "MIT License\n\nCopyright (c) 2026 Upstream Author\n",
    "skills/engineering/tdd/SKILL.md": TDD_SKILL,
    "skills/engineering/tdd/tests.md": "# Good tests\n",
    "skills/engineering/tdd/agents/openai.yaml": "interface: {}\n",
    "skills/engineering/pr/SKILL.md": PR_SKILL,
    "skills/engineering/pr/CREDITS.md": "Dex Horthy\n",
    "skills/other/unused/SKILL.md": "---\nname: unused\ndescription: x\n---\n",
}


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """A checkout of the source repository: upstream's files, as at the lock's commit."""
    source_dir = tmp_path / "source"
    write_files(source_dir, UPSTREAM)
    return source_dir


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """agent-kit/skills/, with one of the foundry's own skills."""
    skills_dir = tmp_path / "agent-kit" / "skills"
    write_files(skills_dir, {"git-conventions/SKILL.md": "# Commit messages\n"})
    return skills_dir


COMMIT = "5beb35b040e3de97e54fa9e386d7e42d15c295c2"


def lock(**skill_paths: str) -> skills.Lock:
    return skills.Lock(
        repo="https://github.com/upstream/skills.git",
        commit=COMMIT,
        license="LICENSE",
        author="Upstream Author",
        license_name="MIT",
        skills=skill_paths or {"tdd": "skills/engineering/tdd", "pr": "skills/engineering/pr"},
    )


# --- install ----------------------------------------------------------------------


def test_a_skill_is_copied_without_its_agents_folder(source_dir, skills_dir) -> None:
    installed = skills.install(lock(), source_dir, skills_dir)

    assert installed == ["tdd", "pr"]
    assert sorted(files_under(skills_dir / "tdd")) == ["SKILL.md", "tests.md"]
    assert body((skills_dir / "tdd" / "SKILL.md").read_text()) == body(TDD_SKILL)
    assert files_under(skills_dir / "pr")["CREDITS.md"] == "Dex Horthy\n"
    assert not (skills_dir / "unused").exists()


def test_the_metadata_names_the_source_and_whether_it_was_adapted(source_dir, skills_dir) -> None:
    skills.install(lock(), source_dir, skills_dir)

    meta = frontmatter((skills_dir / "tdd" / "SKILL.md").read_text())
    assert meta == {
        "name": "tdd",
        "description": "Use when the user wants tests first.",
        "metadata": {
            "source": {
                "repo": "upstream/skills",
                "path": "skills/engineering/tdd",
                "commit": COMMIT,
                "author": "Upstream Author",
                "license": "MIT (see ../LICENSE-upstream)",
            }
        },
    }


def test_existing_metadata_keys_are_kept(source_dir, skills_dir) -> None:
    skills.install(lock(), source_dir, skills_dir)

    meta = frontmatter((skills_dir / "pr" / "SKILL.md").read_text())
    assert meta["metadata"] == {
        "credits": {"author": "Dex Horthy"},
        "source": {
            "repo": "upstream/skills",
            "path": "skills/engineering/pr",
            "commit": COMMIT,
            "author": "Upstream Author",
            "license": "MIT (see ../LICENSE-upstream)",
        },
    }


def test_a_skills_patch_is_applied_and_named_in_its_metadata(source_dir, skills_dir) -> None:
    write_files(skills_dir, {"patches/tdd.patch": TDD_PATCH})

    skills.install(lock(), source_dir, skills_dir)

    skill_md = (skills_dir / "tdd" / "SKILL.md").read_text()
    assert body(skill_md) == "\n# TDD\n\nTake the seams from TASK.md.\n"
    meta = frontmatter(skill_md)
    assert meta["description"] == "Use when a role writes code test-first."
    assert isinstance(meta["metadata"], dict)
    assert meta["metadata"]["adapted"] == "for willcode-foundry; changes in ../patches/tdd.patch"


def test_a_patch_that_doesnt_apply_is_refused_and_nothing_is_changed(source_dir, skills_dir) -> None:
    skills.install(lock(), source_dir, skills_dir)
    write_files(skills_dir, {"patches/pr.patch": TDD_PATCH.replace("tdd", "pr")})
    (source_dir / "skills/engineering/tdd/tests.md").write_text("# Changed upstream\n")
    before = files_under(skills_dir)

    with pytest.raises(FoundryError, match=r"(?s)^skill pr: patches/pr\.patch does not apply: .*SKILL\.md"):
        skills.install(lock(), source_dir, skills_dir)
    assert files_under(skills_dir) == before


def test_files_dropped_upstream_disappear(source_dir, skills_dir) -> None:
    skills.install(lock(), source_dir, skills_dir)
    (source_dir / "skills/engineering/tdd/tests.md").unlink()

    skills.install(lock(), source_dir, skills_dir)

    assert sorted(files_under(skills_dir / "tdd")) == ["SKILL.md"]


def test_installing_twice_changes_nothing(source_dir, skills_dir) -> None:
    write_files(skills_dir, {"patches/tdd.patch": TDD_PATCH})
    skills.install(lock(), source_dir, skills_dir)
    first = files_under(skills_dir)

    skills.install(lock(), source_dir, skills_dir)

    assert files_under(skills_dir) == first


def test_one_of_the_foundrys_own_skills_is_never_overwritten(source_dir, skills_dir) -> None:
    write_files(source_dir, {"skills/engineering/git-conventions/SKILL.md": TDD_SKILL})
    before = files_under(skills_dir)

    with pytest.raises(
        FoundryError, match=r"^skill git-conventions: .*git-conventions has no metadata\.source in its SKILL\.md"
    ):
        skills.install(
            lock(tdd="skills/engineering/tdd", **{"git-conventions": "skills/engineering/git-conventions"}),
            source_dir,
            skills_dir,
        )
    assert files_under(skills_dir) == before


def test_the_licence_is_copied_under_the_source_owners_name(source_dir, skills_dir) -> None:
    skills.install(lock(), source_dir, skills_dir)

    assert (skills_dir / "LICENSE-upstream").read_text() == UPSTREAM["LICENSE"]


@pytest.mark.parametrize(
    ("missing", "message"),
    [
        ("skills/engineering/pr/SKILL.md", r"^skill pr: .*skills/engineering/pr has no SKILL\.md"),
        ("LICENSE", r"^the source has no LICENSE"),
    ],
)
def test_what_the_source_lacks_is_named_and_nothing_is_changed(source_dir, skills_dir, missing, message) -> None:
    (source_dir / missing).unlink()
    before = files_under(skills_dir)

    with pytest.raises(FoundryError, match=message):
        skills.install(lock(), source_dir, skills_dir)
    assert files_under(skills_dir) == before


# --- load_lock --------------------------------------------------------------------


LOCK_YAML = textwrap.dedent(f"""\
    source:
      repo: https://github.com/upstream/skills.git
      commit: {COMMIT}
      license: LICENSE
      author: Upstream Author
      license_name: MIT
    skills:
      tdd: {{path: skills/engineering/tdd}}
      pr: {{path: skills/engineering/pr}}
    """)


def test_the_lock_is_read(tmp_path: Path) -> None:
    (tmp_path / "skills.lock").write_text(LOCK_YAML)

    assert skills.load_lock(tmp_path / "skills.lock") == lock()


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (lambda raw: [raw], "must be a mapping with source and skills"),
        (lambda raw: {"source": raw["source"]}, "must be a mapping with source and skills"),
        (lambda raw: {**raw, "extra": 1}, "must be a mapping with source and skills"),
        (lambda raw: {**raw, "source": {**raw["source"], "commit": "main"}}, "source.commit must be a full"),
        (lambda raw: {**raw, "source": {**raw["source"], "repo": 7}}, "source.repo must be text"),
        (lambda raw: {**raw, "source": {**raw["source"], "unknown": "x"}}, "source must have exactly"),
        (lambda raw: {**raw, "skills": {}}, "skills must map at least one skill"),
        (lambda raw: {**raw, "skills": {"tdd": "skills/tdd"}}, r"skills\.tdd must be \{path: <folder"),
        (lambda raw: {**raw, "skills": {"../x": {"path": "a"}}}, r"'\.\./x' is not a valid skill name"),
        (lambda raw: {**raw, "skills": {"tdd": {"path": "../outside"}}}, r"skills\.tdd\.path must be a relative"),
        (lambda raw: {**raw, "skills": {"patches": {"path": "a"}}}, r"'patches' is not a valid skill name"),
    ],
)
def test_a_malformed_lock_is_refused_naming_the_file_and_the_problem(tmp_path: Path, change, problem) -> None:
    lock_path = tmp_path / "skills.lock"
    lock_path.write_text(yaml.safe_dump(change(yaml.safe_load(LOCK_YAML))))

    with pytest.raises(FoundryError, match=rf"^{re.escape(str(lock_path))}: .*{problem}"):
        skills.load_lock(lock_path)


def test_a_lock_that_is_not_yaml_is_refused(tmp_path: Path) -> None:
    (tmp_path / "skills.lock").write_text("source: [\n")

    with pytest.raises(FoundryError, match=r"skills\.lock is not valid YAML"):
        skills.load_lock(tmp_path / "skills.lock")


# --- fetching the source at a commit ----------------------------------------------


@pytest.fixture
def git_env(tmp_path: Path) -> dict[str, str]:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    (home_dir / ".gitconfig").write_text("[user]\n\tname = Owner\n\temail = owner@example.com\n")
    return {"PATH": os.environ["PATH"], "HOME": str(home_dir), "GIT_CONFIG_NOSYSTEM": "1"}


def test_the_source_is_checked_out_at_the_locks_commit(tmp_path: Path, git_env, skills_dir) -> None:
    origin_dir = tmp_path / "upstream"
    write_files(origin_dir, UPSTREAM)
    for args in (["init", "-q", "-b", "main"], ["add", "."], ["commit", "-qm", "one"]):
        subprocess.run(["git", *args], cwd=origin_dir, env=git_env, check=True, capture_output=True)
    pinned = git(origin_dir, "rev-parse", "HEAD")
    (origin_dir / "skills/engineering/tdd/tests.md").write_text("# Newer than the lock\n")
    subprocess.run(["git", "commit", "-qam", "two"], cwd=origin_dir, env=git_env, check=True, capture_output=True)

    clone_dir = tmp_path / "clone"
    clone_dir.mkdir()
    clone = GitClone.init(f"file://{origin_dir}", clone_dir, git_env)
    clone.check_out_commit(pinned)
    skills.install(lock(), clone_dir, skills_dir)

    assert (skills_dir / "tdd" / "tests.md").read_text() == "# Good tests\n"


def test_a_commit_the_source_doesnt_have_fails_with_gits_message(tmp_path: Path, git_env) -> None:
    origin_dir = tmp_path / "upstream"
    write_files(origin_dir, {"README.md": "x\n"})
    for args in (["init", "-q", "-b", "main"], ["add", "."], ["commit", "-qm", "one"]):
        subprocess.run(["git", *args], cwd=origin_dir, env=git_env, check=True, capture_output=True)
    clone_dir = tmp_path / "clone"
    clone_dir.mkdir()
    clone = GitClone.init(f"file://{origin_dir}", clone_dir, git_env)

    with pytest.raises(FoundryError, match=r"^git fetch failed: "):
        clone.check_out_commit(COMMIT)


# --- the command ------------------------------------------------------------------


def test_the_report_names_the_installed_skills_and_the_commit() -> None:
    assert report(lock(), ["tdd", "pr"]) == [
        f"installed tdd, pr from upstream/skills at {COMMIT[:12]}",
        "review the changes with: git status agent-kit/skills, then commit them",
    ]


def test_update_takes_no_arguments() -> None:
    args = cli.build_parser().parse_args(["skills", "update"])
    assert args.func.__name__ == "update_main"
