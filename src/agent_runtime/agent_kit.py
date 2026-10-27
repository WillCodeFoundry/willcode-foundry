"""Where things sit in the agent kit: the agreement between foundry, which builds into the kit and checks it,
and the runtime, which reads it in the sandbox. Every path inside the kit is spelled here, and only here.

What can't import this names no path in the kit: the git hooks' stubs and the managed settings run the runtime
through the link root mode makes to it (harden.Machine.hooks_runtime_link), and their tests hold them to it.
"""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import ClassVar, Final

RUNTIME_PYZ: Final = PurePosixPath(".build") / "agent_runtime.pyz"
"""Where the built runtime sits, relative to the kit."""

PYTHON: Final = "/usr/bin/python3"
"""The interpreter every call into the runtime uses: the template's own, root-owned, never ``env python3``."""

PYTHON_FLAGS: Final = "-IS"
"""-I ignores PYTHON* variables and user site-packages; -S skips site, so no .pth file runs before the runtime.
One argument, as a shebang line passes."""


@dataclass(frozen=True)
class RoleDir:
    """A role's folder in the kit: its ROLE.md, gitconfig, and skills/, a link to each of its skills."""

    dir: Path

    REQUIRED: ClassVar[tuple[str, ...]] = ("ROLE.md", "gitconfig")
    """What a role's folder must hold. Without gitconfig the agent has no identity; without ROLE.md it starts
    with no role at all, since CLAUDE.md imports it and a missing import is skipped without a word. skills/ is
    optional: a role without it has none."""

    @property
    def role_md(self) -> Path:
        return self.dir / "ROLE.md"

    @property
    def gitconfig(self) -> Path:
        return self.dir / "gitconfig"

    @property
    def skills(self) -> Path:
        return self.dir / "skills"

    def missing(self) -> list[str]:
        """The required files the folder lacks, in REQUIRED's order; empty when it has them all."""
        return [name for name in self.REQUIRED if not (self.dir / name).is_file()]


@dataclass(frozen=True)
class AgentKit:
    """The agent kit in ``dir``, read-only inside a sandbox, mounted at the same path as on the host."""

    dir: Path

    @property
    def runtime(self) -> Path:
        """The built runtime, which every hook and the launch run."""
        return self.dir / RUNTIME_PYZ

    def command(self, *args: str) -> tuple[str, ...]:
        """A call into the runtime, isolated, so nothing the agent sets or installs can shadow it or run first."""
        return (PYTHON, PYTHON_FLAGS, str(self.runtime), *args)

    @property
    def managed_settings(self) -> Path:
        """Claude Code's managed settings, which root mode installs and the check compares with."""
        return self.dir / "claude" / "managed-settings.json"

    @property
    def hooks(self) -> Path:
        """The git hooks' folder, where core.hooksPath points."""
        return self.dir / "hooks"

    @property
    def allowed_signers(self) -> Path:
        """One line per signing role, for verifying commits."""
        return self.dir / "git" / "allowed_signers"

    @property
    def agents_md(self) -> Path:
        """The instructions every role shares."""
        return self.dir / "AGENTS.md"

    @property
    def skills(self) -> Path:
        """Every skill, each in its own folder."""
        return self.dir / "skills"

    def role(self, name: str) -> RoleDir:
        return RoleDir(self.dir / "roles" / name)
