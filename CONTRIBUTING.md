# Contributing

How to develop and test the foundry. Read [ARCHITECTURE.md](ARCHITECTURE.md) first: its design rules apply to every change.

## Development

```console
$ uv sync --group dev
$ uv run pytest                  # the host tier; about 20 seconds
$ uv run pytest -m docker        # the docker tier; needs a Docker daemon
$ uv run pytest -m sbx           # the sbx tier, by hand: see below
$ uv run ruff check . && uv run ruff format --check .
$ uv run mypy
```

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

Shared helpers live in `tests/support/`; the conftests hold only fixtures and pytest hooks. Tests replace the outside world through its one door, never by patching (design rule 3).

`-m docker` and `-m sbx` fail rather than skip when what they need is missing, since you asked for them. The sbx tier runs only when `-m` names it, so a `-m "not docker"` can't launch a real sandbox.

## CI

`.github/workflows/ci.yml` runs lint, mypy and the host tier on the oldest and newest Python, and the docker tier as `sandbox-image`, on every pull request. Its last job, `ci-gate`, passes only if every other job did, and is the check the rulesets require before merging. Add a new job to `ci-gate`'s `needs`, or it won't block anything.

The docker tier pulls the template image by its tag, as sbx does, so a change to the template can turn an unrelated pull request red. Its run ends by naming the image's digest. With the repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` set, the job logs in first, so Docker Hub's rate limit can't fail it.

## Testing against real sbx

`tests/sbx/` launches a real sandbox up to, but not including, attaching the agent. It shows what nothing else can: that sbx accepts the sandbox definition, mounts the kit read-only, runs `session-init` with sudo the first time, and keeps the Docker socket root's after a restart.

- **When:** after upgrading sbx, and before merging changes to `agent-kit/`, `src/agent_runtime/` or `src/foundry/agent_sandbox/`.
- **Prerequisites:** sbx with KVM, signed in; `secrets/ssh/dev` with access to `foundry-test`; and the task, created once with `uv run foundry task create foundry-test sbx-smoke`. The run lists every missing one before any sbx call.
- **What it leaves:** nothing. It removes the sandbox `dev-foundry-test-sbx-smoke` and its session before and after, whatever the outcome. Expect a few minutes.
