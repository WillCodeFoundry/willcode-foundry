from pathlib import Path

import pytest

from foundry import config
from foundry.errors import FoundryError

KEY = "ssh-ed25519 AAAATESTKEY"
REPO_ROOT = Path(__file__).parents[1]


def test_parse_minimal() -> None:
    cfg = config.parse(
        {"name": "x", "signing_key": KEY, "projects": {"p": {"url": "git@h:o/p.git"}}, "roles": {"dev": {}, "qa": None}}
    )
    assert cfg.signing_key == KEY
    assert cfg.project("p").url == "git@h:o/p.git"
    assert cfg.role("dev").name == "dev"
    assert cfg.role("qa").name == "qa"


def test_unknown_project_and_role_are_reported() -> None:
    cfg = config.parse({"name": "x", "signing_key": KEY, "projects": {}, "roles": {"dev": {}}})
    with pytest.raises(FoundryError, match="unknown project 'p'"):
        cfg.project("p")
    with pytest.raises(FoundryError, match="unknown role 'qa'; known: dev"):
        cfg.role("qa")


def test_role_options_are_rejected_not_ignored() -> None:
    with pytest.raises(FoundryError, match="role options are not supported yet"):
        config.parse({"name": "x", "signing_key": KEY, "roles": {"dev": {"memory": "8g"}}})


@pytest.mark.parametrize(
    "raw", [[], "x", {}, {"name": "", "signing_key": KEY}, {"name": "x", "signing_key": KEY, "projects": {"p": {}}}]
)
def test_invalid_shapes(raw: object) -> None:
    with pytest.raises(FoundryError):
        config.parse(raw)


@pytest.mark.parametrize("signing_key", [None, "", 42])
def test_a_signing_key_is_required(signing_key: object) -> None:
    with pytest.raises(FoundryError, match="'signing_key' is required: your SSH public key"):
        config.parse({"name": "x", "signing_key": signing_key})


def test_the_instances_signing_key_is_one_allowed_signers_lists() -> None:
    signing_key = config.load(REPO_ROOT / "config" / "foundry.yaml").signing_key
    allowed = (REPO_ROOT / "agent-kit" / "git" / "allowed_signers").read_text().splitlines()
    assert any(line.split(maxsplit=1)[1:] == [signing_key] for line in allowed if not line.startswith("#"))
