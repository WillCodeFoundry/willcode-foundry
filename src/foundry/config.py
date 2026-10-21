"""config/foundry.yaml: the instance's registry of projects and roles."""

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
    name: str
    projects: dict[str, Project]
    roles: dict[str, Role]

    def project(self, name: str) -> Project:
        try:
            return self.projects[name]
        except KeyError:
            raise FoundryError(f"unknown project {name!r}; known: {', '.join(sorted(self.projects)) or 'none'}") from None

    def role(self, name: str) -> Role:
        try:
            return self.roles[name]
        except KeyError:
            raise FoundryError(f"unknown role {name!r}; known: {', '.join(sorted(self.roles)) or 'none'}") from None


def load(path: Path) -> Config:
    return parse(yaml_io.load(path), source=str(path))


def parse(raw: object, *, source: str = "config") -> Config:
    if not isinstance(raw, dict):
        raise FoundryError(f"{source}: top level must be a mapping")
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise FoundryError(f"{source}: 'name' is required")

    projects: dict[str, Project] = {}
    for key, value in (raw.get("projects") or {}).items():
        if not isinstance(value, dict) or not isinstance(value.get("url"), str):
            raise FoundryError(f"{source}: projects.{key} needs a 'url'")
        projects[key] = Project(name=key, url=value["url"])

    roles: dict[str, Role] = {}
    for key, value in (raw.get("roles") or {}).items():
        if value:
            raise FoundryError(f"{source}: roles.{key}: role options are not supported yet; use {{}}")
        roles[key] = Role(name=key)

    return Config(name=name, projects=projects, roles=roles)
