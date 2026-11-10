# Working on the foundry

These instructions are for changing this repository. Agents working inside a sandbox are given `agent-kit/AGENTS.md` instead.

## Before changing code

Read the design rules in [ARCHITECTURE.md](ARCHITECTURE.md#design-rules), and follow them. Use the words in [GLOSSARY.md](GLOSSARY.md), and check [docs/adr/](docs/adr/README.md) before reversing how something works: a decision recorded there changes only through a new ADR that supersedes it.

## Checks

Run ruff before every commit, and the host tier and the other static checks before every push, as an ordinary user, never as root. `.pre-commit-config.yaml` runs them for you once installed. [CONTRIBUTING.md](CONTRIBUTING.md) has the commands, and says when to run the docker and sbx tiers too.

The only shell scripts are the git hook stubs in `agent-kit/hooks/`. Everything else that runs in a sandbox is the runtime, in Python.

## Docs

Write each fact once, in the place closest to the code that keeps it true:

| Fact | Where |
|---|---|
| What a function or class does, takes or refuses | Its docstring |
| What holds across a module, and why | The module docstring, after a one-line purpose |
| What each module is for | Its row in [ARCHITECTURE.md's codemap](ARCHITECTURE.md#codemap) |
| A rule for all the code | A [design rule](ARCHITECTURE.md#design-rules), cited by number rather than restated |
| A decision that is hard to reverse | An ADR, as below |

A module docstring doesn't list what its module holds, as [python-smells 8.4](agent-kit/skills/python-smells/references/narrating-instead-of-naming.md) says.

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
