from pathlib import Path

import pytest

from foundry.agent_sandbox import SandboxDefinition, valid_sandbox_name
from foundry.agent_sandbox.errors import SandboxError

DEFINITION = SandboxDefinition(
    name="dev-p-t1",
    workspace_dir=Path("/tmp/ws"),
    agent_kit_dir=Path("/f/agent-kit"),
    variables={"AGENT_ROLE": "dev", "AGENT_TASK": "T1"},
)


def test_a_written_definition_reads_back_the_same(tmp_path: Path) -> None:
    DEFINITION.write(tmp_path)
    assert SandboxDefinition.read(tmp_path) == DEFINITION


def test_it_is_written_in_sbxs_schema(tmp_path: Path) -> None:
    DEFINITION.write(tmp_path)
    assert (tmp_path / SandboxDefinition.FILE_NAME).read_text() == (
        "schemaVersion: '1'\n"
        "name: dev-p-t1\n"
        "agent: claude\n"
        "workspace: /tmp/ws\n"
        "additionalWorkspaces:\n"
        "- path: /f/agent-kit\n"
        "  readOnly: true\n"
        "env:\n"
        "  AGENT_ROLE: dev\n"
        "  AGENT_TASK: T1\n"
    )


@pytest.mark.parametrize(
    "content",
    [
        "name: x\nworkspace: /w\nenv: {}\n",  # no additionalWorkspaces
        "name: x\nworkspace: /w\nenv: {}\nadditionalWorkspaces: []\n",  # no agent kit
        "[]\n",
        "name: [unclosed\n",
    ],
)
def test_anything_foundry_did_not_write_fails_in_one_line(tmp_path: Path, content: str) -> None:
    (tmp_path / SandboxDefinition.FILE_NAME).write_text(content)
    with pytest.raises(SandboxError, match=r"sbxenv.yaml: not a sandbox definition written by foundry \("):
        SandboxDefinition.read(tmp_path)


def test_a_missing_definition_says_so(tmp_path: Path) -> None:
    with pytest.raises(SandboxError, match=r"sbxenv.yaml is missing"):
        SandboxDefinition.read(tmp_path)


@pytest.mark.parametrize("name", ["dev-p-t1", "a.b+c", "x" * 64])
def test_names_sbx_accepts(name: str) -> None:
    assert valid_sandbox_name(name)


@pytest.mark.parametrize("name", ["", "dev p", "dev/p", "x" * 65])
def test_names_sbx_or_the_ssh_agent_socket_refuse(name: str) -> None:
    """The name also names the sandbox's ssh-agent socket, whose path is limited."""
    assert not valid_sandbox_name(name)


def test_a_definition_refuses_a_name_sbx_wouldnt_accept() -> None:
    with pytest.raises(SandboxError, match="isn't a sandbox name sbx accepts"):
        SandboxDefinition(name="dev p", workspace_dir=Path("/w"), agent_kit_dir=Path("/k"), variables={})
