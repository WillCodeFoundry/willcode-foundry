# Contributing

How to develop and test the foundry. Read [ARCHITECTURE.md](ARCHITECTURE.md) first: its design rules apply to every change.

## Development

### Set up the development environment

Install the dev dependencies (pytest, ruff, mypy) before running any check:

```console
$ uv sync --group dev
```

They aren't installed by default, since `pyproject.toml` sets `default-groups = []`. A plain `uv sync` removes them again, so run this one after it.

### Run the tests and checks

```console
$ uv run pytest                  # the host tier; about 20 seconds
$ uv run pytest -m docker        # the docker tier; needs a Docker daemon
$ uv run pytest -m sbx           # the sbx tier, by hand: see below
$ uv run ruff check . && uv run ruff format --check .
$ uv run mypy
$ uv run vulture                        # unused code in src/
$ uv run pylint src                     # duplicated code in src/
$ uv run shellcheck agent-kit/hooks/*   # the hook stubs
```

### What the static checks catch

The checks hold the smells a tool can see. Code review holds the rest.

| Check | Catches |
|---|---|
| `ruff check` | unused parameters, blanket and silent `except`, `assert` in `src/`, functions past the size limits, boolean flag parameters, private access across objects, `print` outside the entry points, commented-out code, blanket `noqa` and `type: ignore`, unsafe calls, too-broad `pytest.raises`, and `unittest.mock` in tests |
| `mypy` | strict typing, plus unreachable code, redundant checks, conditions that are always true, and an `ignore` without its error code |
| `vulture` | functions, classes and attributes in `src/` that nothing uses |
| `pylint src` | the same five or more lines in two places in `src/`; it runs only this check |
| `shellcheck` | mistakes in the hook stubs, the only shell scripts |
| `tests/test_defensive_reads.py` | `getattr` or `hasattr` with a literal attribute name in `src/` |

`pyproject.toml` says why each rule is on, and why each exception is off. Silence a finding on one line with `# noqa: <code>` and the reason.

### Run them before you push

`.pre-commit-config.yaml` runs ruff before each commit, and the rest of the checks and the host tier before each push. Install it once, in your checkout:

```console
$ uvx pre-commit install
```

Sandboxed agents use the kit's hooks instead, so they run the checks themselves, as `AGENTS.md` says.

Run the tests as an ordinary user. A run started as root stops before collecting anything, since root can write anything and the permission checks would mean nothing.

## Test tiers

Each behaviour is tested once, at the cheapest tier that can catch its bug. A higher tier tests only what the lower ones can't, and says so in its docstring.

| Tier | Folder | Covers | Runs |
|---|---|---|---|
| host | `tests/` (top level) | foundry: config, sessions, tasks, the runtime build, skills, the repo policy, and the docs | every `uv run pytest`; CI |
| host | `tests/agent_sandbox/` | the sbx calls, against fakes of the host and sbx | every `uv run pytest`; CI |
| host | `tests/agent_runtime/` | every rule in the runtime, in-process; hardening runs against a modelled machine ([ADR 0009](docs/adr/0009-test-against-a-modelled-machine.md)) | every `uv run pytest`; CI |
| host | `tests/agent_kit/` | only what the kit as delivered shows: the built runtime, the stubs, the managed settings' commands | every `uv run pytest`; CI |
| docker | `tests/sandbox_image/` | `session-init` and the git hooks in the template image: real hardening, permissions and read-only mount | `-m docker`; CI's `sandbox-image` job |
| sbx | `tests/sbx/` | a real sandbox: launch, relaunch, restart | `-m sbx`, by hand |

Shared helpers live in `tests/support/`; the conftests hold only fixtures and pytest hooks. Tests never patch: they fake GitHub and the host, run real git in temporary repositories, and put stand-in executables on `PATH` (design rule 3).

`-m docker` and `-m sbx` fail rather than skip when what they need is missing, since you asked for them. The sbx tier runs only when `-m` names it, so a `-m "not docker"` can't launch a real sandbox.

## CI

`.github/workflows/ci.yml` runs on every pull request and every push to main. It runs lint and mypy, the host tier on the oldest and newest Python the foundry supports, and the docker tier as `sandbox-image`. Its last job, `ci-gate`, passes only if every other job did, and is the check the rulesets require before merging. Add a new job to `ci-gate`'s `needs`, or it won't block anything.

The docker tier pulls the template image by its tag, as sbx does, so a change to the template can turn an unrelated pull request red. Its run ends by naming the image's digest. With the repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` set, a read-only token, the job logs in first, so Docker Hub's anonymous rate limit can't fail it.

## Testing against real sbx

`tests/sbx/` launches a real sandbox up to, but not including, attaching the agent. It shows what nothing else can: that sbx accepts the sandbox definition, mounts the kit read-only, runs `session-init` with sudo the first time, and keeps the Docker socket root's after a restart.

- **When:** after upgrading sbx, and before merging changes to `agent-kit/`, `src/agent_runtime/` or `src/foundry/agent_sandbox/`.
- **Prerequisites:** sbx with KVM, signed in; `secrets/ssh/dev` with access to `foundry-test`; and the task, created once with `uv run foundry task create foundry-test sbx-0001`. The run lists every missing one before any sbx call.
- **What it leaves:** nothing. It removes the sandbox `dev-foundry-test-sbx-0001` and its session before and after, whatever the outcome. Expect a few minutes.
