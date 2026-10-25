"""config/foundry.yaml: the instance's registry of projects and roles."""

from dataclasses import dataclass
from pathlib import Path

from foundry import paths, yaml_io
from foundry.errors import FoundryError


@dataclass(frozen=True)
class Project:
    name: str
    url: str


@dataclass(frozen=True)
class Role:
    """A role an agent can be given, as this foundry has it.

    Listed in config/foundry.yaml, with its folder in the agent kit (load refuses one
    without); its SSH key and, if it should have gh, its GitHub token, under secrets/.
    """

    name: str
    ssh_key_path: Path
    """The role's private key. Not checked here: the launcher refuses a launch without it."""
    github_token_path: Path | None
    """None unless secrets/github/<role>.token exists: a role gets a token only if you give it one."""


@dataclass(frozen=True)
class Config:
    foundry_name: str
    projects: dict[str, Project]
    roles: dict[str, Role]

    def project(self, project_name: str) -> Project:
        """The project of that name; raises if config/foundry.yaml doesn't list it."""
        try:
            return self.projects[project_name]
        except KeyError:
            known = ", ".join(sorted(self.projects)) or "none"
            raise FoundryError(f"unknown project {project_name!r}; known: {known}") from None

    def role(self, role_name: str) -> Role:
        """The role of that name; raises if config/foundry.yaml doesn't list it."""
        try:
            return self.roles[role_name]
        except KeyError:
            known = ", ".join(sorted(self.roles)) or "none"
            raise FoundryError(f"unknown role {role_name!r}; known: {known}") from None


def load(foundry_root: Path) -> Config:
    """The foundry's config/foundry.yaml, with each role's files as this foundry has them."""
    config_path = paths.config_path(foundry_root)
    return parse(yaml_io.load(config_path), foundry_root=foundry_root, source=str(config_path))


def parse(raw: object, *, foundry_root: Path, source: str = "config") -> Config:
    if not isinstance(raw, dict):
        raise FoundryError(f"{source}: top level must be a mapping")
    foundry_name = raw.get("name")
    if not isinstance(foundry_name, str) or not foundry_name:
        raise FoundryError(f"{source}: 'name' is required")

    projects: dict[str, Project] = {}
    for project_name, value in (raw.get("projects") or {}).items():
        if not isinstance(value, dict) or not isinstance(value.get("url"), str):
            raise FoundryError(f"{source}: projects.{project_name} needs a 'url'")
        projects[project_name] = Project(name=project_name, url=value["url"])

    roles: dict[str, Role] = {}
    for role_name, value in (raw.get("roles") or {}).items():
        if value:
            raise FoundryError(f"{source}: roles.{role_name}: role options are not supported yet; use {{}}")
        roles[role_name] = _role(foundry_root, role_name, source=source)

    return Config(foundry_name=foundry_name, projects=projects, roles=roles)


# What a role's folder in the agent kit must hold. session-setup fails without the gitconfig, and
# without ROLE.md the agent starts with no role at all: CLAUDE.md imports it, and a missing import
# is skipped without a word. skills/ is optional: a role without it has none.
_ROLE_FILES = ("ROLE.md", "gitconfig")


def _role(foundry_root: Path, role_name: str, *, source: str) -> Role:
    """The role, refused unless its folder in the agent kit holds what a sandbox needs from it."""
    role_dir = paths.role_dir(foundry_root, role_name)
    if not role_dir.is_dir():
        raise FoundryError(f"{source}: role {role_name!r} has no folder in the agent kit: {role_dir} doesn't exist")
    missing = [name for name in _ROLE_FILES if not (role_dir / name).is_file()]
    if missing:
        raise FoundryError(f"{source}: role {role_name!r}: {role_dir} has no {' or '.join(missing)}")
    github_token_path = paths.github_token_path(foundry_root, role_name)
    return Role(
        name=role_name,
        ssh_key_path=paths.ssh_key_path(foundry_root, role_name),
        github_token_path=github_token_path if github_token_path.is_file() else None,
    )
