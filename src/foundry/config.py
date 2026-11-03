"""config/foundry.yaml: the instance's registry of projects and roles."""

import re
from dataclasses import dataclass
from pathlib import Path

from agent_runtime.agent_kit import AgentKit
from foundry import paths, yaml_io
from foundry.errors import FoundryError

# A model as Claude Code's --model takes it: an alias (opus, sonnet[1m]) or a full name (claude-opus-5-5). Starting
# with a letter or digit, so it can't be read as another option.
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:\[\]-]*")


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
    model: str | None = None
    """The model its agent runs on, passed to Claude Code at each launch; None for Claude Code's default."""


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
        model = _role_model(value, f"{source}: roles.{role_name}")
        roles[role_name] = _role(foundry_root, role_name, model=model, source=source)

    return Config(foundry_name=foundry_name, projects=projects, roles=roles)


def _role_model(options: object, where: str) -> str | None:
    """The model a role's options name, or None when they name none. Refuses any other option, and a model
    Claude Code's --model couldn't take."""
    if options is None:
        return None
    if not isinstance(options, dict):
        raise FoundryError(f"{where} must be a mapping, such as {{}} or {{model: opus}}")
    if unknown := sorted(set(options) - {"model"}):
        raise FoundryError(f"{where}: unknown role option {unknown[0]!r}; the only one is 'model'")
    model = options.get("model")
    if model is None:
        return None
    if not isinstance(model, str) or not _MODEL.fullmatch(model):
        raise FoundryError(
            f"{where}.model {model!r} is not a model: use an alias or a full name, such as opus or claude-opus-5-5"
        )
    return model


def _role(foundry_root: Path, role_name: str, *, model: str | None, source: str) -> Role:
    """The role, refused unless its folder in the agent kit holds what a sandbox needs from it: the rule is
    agent_kit's, which session-setup applies again in the sandbox."""
    role_dir = AgentKit(paths.agent_kit_dir(foundry_root)).role(role_name)
    if not role_dir.dir.is_dir():
        raise FoundryError(f"{source}: role {role_name!r} has no folder in the agent kit: {role_dir.dir} doesn't exist")
    if missing := role_dir.missing():
        raise FoundryError(f"{source}: role {role_name!r}: {role_dir.dir} has no {' or '.join(missing)}")
    github_token_path = paths.github_token_path(foundry_root, role_name)
    return Role(
        name=role_name,
        ssh_key_path=paths.ssh_key_path(foundry_root, role_name),
        github_token_path=github_token_path if github_token_path.is_file() else None,
        model=model,
    )
