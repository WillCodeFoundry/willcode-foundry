"""agent-kit/git/allowed_signers lists every role's signing identity, as its gitconfig sets it."""

import subprocess
from pathlib import Path

import pytest

AGENT_KIT_PATH = Path(__file__).parents[2] / "agent-kit"
ALLOWED_SIGNERS_PATH = AGENT_KIT_PATH / "git" / "allowed_signers"
ROLE_GITCONFIG_PATHS = sorted((AGENT_KIT_PATH / "roles").glob("*/gitconfig"))


def allowed_signers() -> set[tuple[str, str]]:
    """(email, public key) per line, without comments."""
    lines = [line.split() for line in ALLOWED_SIGNERS_PATH.read_text().splitlines() if line and line[0] != "#"]
    return {(fields[0], " ".join(fields[1:3])) for fields in lines}


def gitconfig_value(gitconfig_path: Path, key: str) -> str:
    result = subprocess.run(
        ["git", "config", "--file", str(gitconfig_path), key], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def test_every_role_that_starts_a_session_has_a_gitconfig() -> None:
    roles = {path.name for path in (AGENT_KIT_PATH / "roles").iterdir() if (path / "ROLE.md").is_file()}
    assert roles == {path.parent.name for path in ROLE_GITCONFIG_PATHS}


@pytest.mark.parametrize("gitconfig_path", ROLE_GITCONFIG_PATHS, ids=lambda path: path.parent.name)
def test_each_roles_signing_identity_is_an_allowed_signer(gitconfig_path: Path) -> None:
    email = gitconfig_value(gitconfig_path, "user.email")
    key = gitconfig_value(gitconfig_path, "user.signingkey").removeprefix("key::")
    assert (email, key) in allowed_signers()
