# Python specifics

Read this alongside `checklist.md` when the code under review is Python. It maps the general smells to Python idioms and tools.

## Tools for stages 1 and 2

Use what the project already has installed before adding anything. Run each tool through the project's environment runner (`uv run`, `poetry run`, `hatch run`, or the activated virtualenv).

| Purpose | Tool | Notes |
|---|---|---|
| Rank functions by complexity | `scripts/complexity.py src/ scripts/` | Bundled with this skill. It also finds extensionless scripts with a python shebang |
| Complexity as lint rules | `ruff check --select C901,PLR0911,PLR0912,PLR0913,PLR0915` | Too complex, too many returns, branches, arguments or statements |
| Uncalled functions and classes | `vulture`, plus `git grep -nw <name>` | Search before inlining or deleting: vulture misses dynamic uses (`getattr`, entry points, plugin registries) |
| Unused imports and variables | `ruff check --select F401,F841` | Useful after moves and inlines, not for finding uncalled helpers |
| Type holes | `mypy --strict`, or `pyright` | `Any`, `cast` and `# type: ignore` mark places where structure is hidden |
| Package boundaries and import direction | `import-linter` contracts, or a small `ast` test | Turns "imports nothing from X" or "domain doesn't import adapters" into a checked fact |
| Test coverage of code to be moved | `pytest --cov=<package> --cov-report=term-missing` | Run it before agreeing a refactor: see "Refactoring safely" |
| Mechanical renames and moves | IDE refactoring, or `rope` | Safer than search-and-replace for names that are also common words |

## Refactoring safely

- **Check coverage first.** A mechanical change is only behaviour-preserving if tests exercise the code being renamed or moved. Where coverage is missing, make the brief's first commit add characterisation tests that pin the current behaviour.
- **Decide what is public API.** It includes names in `__all__`, documented imports, console-script entry points, and anything a published package exports.
  - In an **application**, renaming them is internal.
  - In a **published library**, a rename needs an alias that emits `DeprecationWarning`, or a major version bump. Say which applies in the proposal.
- **Watch for tests coupled to import paths.** `mock.patch("pkg.module.func")` names where a function is looked up, so moving the function breaks the test even when behaviour is unchanged. Flag these, and prefer fakes injected through constructor parameters or `Protocol`-typed arguments. If they stay, the brief must list the patch targets that change.
- **Take small steps.** Every commit in the brief should leave tests, lint and types green.

## Architecture in Python

- **Dependency direction.** Domain modules (rules, models, calculations) shouldn't import adapter modules (HTTP clients, database access, `subprocess`, filesystem helpers). Check with `import-linter` layers or by reading the imports at the top of each module. An adapter imported into the domain to get a constant or a type usually means that thing belongs in the domain.
- **A composition root.** Real implementations should be created and wired together once, in the entry point (`main()`, the CLI handler, the app factory), and passed down. Module-level instances, singletons, and functions that build their own clients make substitution and testing hard.
- **A functional core with an imperative shell.** Pure functions that take data and return data are easy to test and to move. Look for logic tangled with I/O that could be split into "fetch", "decide" and "act".
- **Parse, don't validate.** Convert external input (files, HTTP, the environment, CLI arguments) into typed objects (dataclasses, enums, or pydantic models where already used) once, at the boundary. Code past the boundary then trusts its types, and the over-defensive checks in checklist 9 go away.
- **Circular imports** (or imports moved inside functions to avoid them) usually mean a boundary is drawn in the wrong place. Find the shared concept and give it its own module.

## Python forms of the checklist smells

**Names (checklist 1–3)**
- Follow PEP 8: `snake_case` for modules, functions and variables, `CapWords` for classes, `UPPER_CASE` for constants.
- Module names are short, lowercase nouns for the subject. Avoid `utils.py`, `helpers.py`, `common.py` and `misc.py`.
- A leading `_` marks a name as private to its module. A private name imported from another module is a structure smell: either it isn't private, or the caller is in the wrong place.
- `__all__` in a package's `__init__.py` defines its public names. Check that the call sites read well with them (`billing.charge(billing.ChargeRequest(...))`).
- A parameter that shadows a builtin (`id`, `type`, `input`, `list`) or a module-level function is a rename candidate.

**Modelling and types (checklist 4 and 5)**
- **Dicts with a fixed set of keys** that travel between functions (`TypedDict` plus `cast`, or `dict[str, Any]`) usually want to be a `@dataclass(frozen=True)`, with `slots=True` where many instances exist. Accessor functions over the dict then become fields. Keep `TypedDict` for data that really is a dict on the wire, such as JSON payloads, at the boundary only.
- **A closed set of string values** (states, modes, kinds) wants an `enum.Enum`, or a `StrEnum` when the strings must round-trip, rather than module-level string constants.
- **Parameter types:** accept the most general type you use (`Iterable`, `Sequence`, `Mapping`) and return the concrete type you build (`list`, `dict`). Mark module constants `Final` where the project uses strict typing.
- **`**kwargs: Any` in an internal API** hides which arguments are allowed. Make them explicit, or pass a dataclass.
- **Module-level side effects at import** (reading files, network calls, configuring logging) belong in a function called from the entry point.
- **Exceptions:** one base class per package (a `<Package>Error`), with subclasses only where a caller handles them differently, caught once at the entry point. Two identical base classes are justified only if the package boundary is real (checklist 4). Use `raise … from error` to keep the cause, or `from None` when it adds nothing.
- **Output:** library code logs through `logging.getLogger(__name__)`. `print` belongs in the CLI layer only.

**Ports (checklist 6)**
- Use `typing.Protocol` for a port the domain defines, and plain classes for implementations. Prefer `Protocol` to `abc.ABC` unless implementations share code. Don't suffix either with `Port`, `Adapter` or `Impl`.
- In the tests, a fake that subclasses the real class instead of implementing the `Protocol` is the signal described in checklist 6.
- A port defined as a `Callable` over shell-command strings (a "runner") is usually at the wrong level. Prefer methods named after the service's operations.
- Inject ports through constructor or function parameters, not by patching module attributes in tests. See `testing.md` section 9 for the pattern and the acceptable exceptions.

**Over-defensive code (checklist 9)**
- Watch for `isinstance` chains, `.get(key) or default`, and `try: ... except (KeyError, TypeError, IndexError)` used to validate data the program wrote itself.
- The loud-failure version is one `try` around constructing the dataclass, re-raised once as the package's error with the file path in the message.
- `except Exception:` or a bare `except:` that swallows the error is a smell. Re-raising after cleanup is fine.
- Exceptions raised only to jump to an `except` in the same function (`raise TypeError` inside a `try` purely to reach the handler) are control flow by exception. Use an `if`.

**Control flow (checklist 10)**
- A function returning `X | None` where `None` means "no difference" or "nothing to report" reads well at call sites: `if (difference := compare(...)) is not None:`.
- For argparse CLIs, a `set_defaults(func=...)` per subcommand is fine. Signatures that force every handler to accept arguments only one uses are the smell.

## Things not to flag in Python

- **`from __future__ import annotations`, or string annotations,** used to avoid runtime import cost or cycles in type hints.
- **Short repeated `try/except KeyError` lookups** whose error messages differ. Repetition that is easy to understand is fine (checklist 7).
- **`pathlib.Path` versus `os.path`.** Flag only a codebase that mixes the two for the same job; then recommend `pathlib`.
- **Style that a formatter or linter already enforces** (line length, import order, quote style). Mention a missing formatter once, if at all.
