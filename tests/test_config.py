import pytest

from foundry import config
from foundry.errors import FoundryError


def test_parse_minimal() -> None:
    cfg = config.parse({"name": "x", "projects": {"p": {"url": "git@h:o/p.git"}}, "roles": {"dev": {}, "qa": None}})
    assert cfg.project("p").url == "git@h:o/p.git"
    assert cfg.role("dev").role_name == "dev"
    assert cfg.role("qa").role_name == "qa"


def test_unknown_project_and_role_are_reported() -> None:
    cfg = config.parse({"name": "x", "projects": {}, "roles": {"dev": {}}})
    with pytest.raises(FoundryError, match="unknown project 'p'"):
        cfg.project("p")
    with pytest.raises(FoundryError, match="unknown role 'qa'; known: dev"):
        cfg.role("qa")


def test_role_options_are_rejected_not_ignored() -> None:
    with pytest.raises(FoundryError, match="role options are not supported yet"):
        config.parse({"name": "x", "roles": {"dev": {"memory": "8g"}}})


@pytest.mark.parametrize("raw", [[], "x", {}, {"name": ""}, {"name": "x", "projects": {"p": {}}}])
def test_invalid_shapes(raw: object) -> None:
    with pytest.raises(FoundryError):
        config.parse(raw)
