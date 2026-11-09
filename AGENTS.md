# Working on the foundry

These instructions are for changing this repository. Agents working inside a sandbox are given `agent-kit/AGENTS.md` instead.

## Before changing code

Read the design rules in [ARCHITECTURE.md](ARCHITECTURE.md#design-rules), and follow them. Use the words in [GLOSSARY.md](GLOSSARY.md), and check [docs/adr/](docs/adr/README.md) before reversing how something works: a decision recorded there changes only through a new ADR that supersedes it.

## Checks

Run ruff before every commit, and the host tier and the other static checks before every push, as an ordinary user, never as root. `.pre-commit-config.yaml` runs them for you once installed. [CONTRIBUTING.md](CONTRIBUTING.md) has the commands, and says when to run the docker and sbx tiers too.

The tools hold only the smells they can see. Before every commit, check your diff against the [python-smells](agent-kit/skills/python-smells/SKILL.md) and [python-naming-smells](agent-kit/skills/python-naming-smells/SKILL.md) skills too.

The only shell scripts are the git hook stubs in `agent-kit/hooks/`. Everything else that runs in a sandbox is the runtime, in Python.

## Code

- **A check that raises is named `require_<what must hold>`**, with a leading underscore when private. It returns None, and raises where it finds the problem, as `_require_own_kit` in `src/foundry/session.py` does.
- **Don't hand a failure to the caller to raise.** No function returns a reason for its caller to raise, and no helper builds an exception for another function to raise. [python-smells](agent-kit/skills/python-smells/references/hiding-failure.md) 3.8 says why.

## Docs

- **Record a decision as an ADR** when it is hard to reverse, surprising without context, and the result of a real trade-off. Use the next number in `docs/adr/`.
- **Add a term to the glossary** when you introduce one, or when you find one word used for two things.
- **Keep the README's "Recreating a sandbox" heading.** Error messages send users there. `tests/test_docs.py` checks this. It also checks that every link resolves, that every repository path the docs name exists, and that the command tables match the commands the code defines.

## Writing

For every doc, docstring and message:

- The first sentence says the point.
- Keep sentences under about 25 words, and paragraphs to three sentences.
- Use a table or a list for anything shaped like one.
- Name the module or file instead of retelling what it does.
- Give each reason its own sentence, rather than chaining reasons behind colons.
