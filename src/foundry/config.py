"""config/foundry.yaml: the instance's registry of projects and roles, and your signing key."""

from dataclasses import dataclass
from pathlib import Path

from foundry import yaml_io
from foundry.errors import FoundryError


@dataclass(frozen=True)
class Project:
    name: str
    url: str


@dataclass(frozen=True)
class Role:
    name: str


@dataclass(frozen=True)
class Config:
    foundry_name: str
    signing_key: str  # your SSH public key, as in agent-kit/git/allowed_signers: signs commits foundry makes as you
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


def load(config_path: Path) -> Config:
    return parse(yaml_io.load(config_path), source=str(config_path))


def parse(raw: object, *, source: str = "config") -> Config:
    if not isinstance(raw, dict):
        raise FoundryError(f"{source}: top level must be a mapping")
    foundry_name = raw.get("name")
    if not isinstance(foundry_name, str) or not foundry_name:
        raise FoundryError(f"{source}: 'name' is required")
    signing_key = raw.get("signing_key")
    if not isinstance(signing_key, str) or not signing_key:
        raise FoundryError(
            f"{source}: 'signing_key' is required: your SSH public key (ssh-ed25519 AAAA...), "
            "as in agent-kit/git/allowed_signers, whose private half is in your ssh-agent"
        )

    projects: dict[str, Project] = {}
    for project_name, value in (raw.get("projects") or {}).items():
        if not isinstance(value, dict) or not isinstance(value.get("url"), str):
            raise FoundryError(f"{source}: projects.{project_name} needs a 'url'")
        projects[project_name] = Project(name=project_name, url=value["url"])

    roles: dict[str, Role] = {}
    for role_name, value in (raw.get("roles") or {}).items():
        if value:
            raise FoundryError(f"{source}: roles.{role_name}: role options are not supported yet; use {{}}")
        roles[role_name] = Role(name=role_name)

    return Config(foundry_name=foundry_name, signing_key=signing_key, projects=projects, roles=roles)
