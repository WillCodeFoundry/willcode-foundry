# Review checklist

Apply every section. Each smell has a way to detect it and a usual fix. Report a smell only when you have evidence for it, and only when it matters in practice.

The examples use Python-like syntax for illustration. Translate them into the idioms of the language you're reviewing: for instance, packages and classes in Java, modules and structs in Go and Rust, or modules and exports in TypeScript.

## Contents

1. Names that don't match behaviour
2. Explicit but not repetitive
3. One word per concept
4. Module and package structure
5. Single responsibility
6. Ports and adapters, without naive renaming
7. DRY, within reason
8. Trivial helpers
9. Over-defensive code
10. Control-flow smells
11. Stale text
12. Dependencies and testability

## 1. Names that don't match behaviour

- **The name of a query or builder sounds like an action.**
  - Detect: read the body. A `send_email()` that only builds the message and returns it.
  - Fix: name the result, e.g. `build_email()`.
- **A constant's name claims more than its value.**
  - Detect: follow the value to where it's used. A `CACHE_DIR` that another module appends a user id to, so it is really a prefix.
  - Fix: build the whole value in one function, in the module that owns it.
- **A function's name describes one case of what it does.**
  - Detect: a `merge(items)` that merges mappings but returns the first item for anything else.
  - Fix: name what it produces for its callers.
- **A name collides with the domain's main noun.**
  - Detect: list the domain nouns, then search for functions named after them. In an ordering system, `order(items)` meaning "sort" reads as "an order of items".
  - Fix: use a verb phrase that can't be confused with the noun, e.g. `sort_by_priority(items)`.
- **A misleading abbreviation.**
  - Detect: ask what a newcomer would assume. "env file" suggests `.env` and environment variables; "ctx" or "mgr" says nothing.
  - Fix: use the term the project's docs or users already use.
- **A generic module name.**
  - Detect: the name would fit in any codebase (`utils`, `common`, `helpers`, `manager`, `data`, `standard`, `core`, `misc`).
  - Fix: say what kind of thing, and for what, e.g. `invoice_rules` rather than `rules`.
- **A module and a class share a name, and the word is also a verb.**
  - Detect: code reads like `upload.Upload`, with `process(upload)` inside a module called `upload`.
  - Fix: name the module after its role (`uploader`) and the class after what it carries (`UploadRequest`). Functions inside the module then drop their redundant suffixes.
- **"ensure" (or "validate", "check") names a function that behaves differently than the word promises.**
  - Detect: an `ensure_x()` that never changes anything and only raises, or a `check_x()` that also fixes things.
  - Fix: adopt one convention and apply it everywhere. For example, `ensure_` makes something so; `require_` checks and raises.

## 2. Explicit but not repetitive

- **Attributes that repeat their class:** `User.user_name`, `Order.order_id`. Use `.name` and `.id`.
  - **Exception:** keep the qualifier when the attribute names a *different* thing from its object. On a `Config` describing an application instance, `app_name` is the name of the app, not of the config, so `config.name` would be ambiguous.
- **Constants named after their own value:** `USER_ID_KEY = "USER_ID"`. If the literal itself is the contract (other programs, scripts or docs use it directly), inline it.
- **Double or inconsistent suffixes:** `output_dir_path` next to `input_path` for another directory. Pick one convention, such as `_dir` for directories and `_path` for files, ideally matching names the project already exposes (environment variables, CLI flags). Words that already imply a directory, like `root`, need no suffix.
- **A parameter that shadows a module-level function of the same name:** a method parameter `slug` beside a function `slug(url)`. Rename the function after what it does, e.g. `slug_from_url`.

## 3. One word per concept

- **Several words for one role.** For example, `template`, `reference` and `baseline` all meaning "the expected value" in one module. Pick one (`expected`) and use it everywhere.
- **One concept under two names.** For example, a call like `cache_path=storage_dir`.
- **Two concepts under one name.** Two functions both called `config_path`: one computes where the config should be, the other reads where an existing deployment says it is.
- **Several nouns for one lifecycle.** For example, job, run, task and execution used loosely for the same thing. Write a glossary that gives each word one meaning, then rename to match. A new name must not bring back a word the glossary left out.

## 4. Module and package structure

- **One module per subject.** If understanding one subject ("what makes an invoice valid") means reading two modules, one for parsing and one for rules, split by subject instead of by layer.
- **A module named for where its data comes from** (`api_responses`, `db_rows`, `file_contents`) rather than what it's about. Rename it after the subject.
- **A package boundary only half kept.**
  - Detect: a package documented as independent ("imports nothing from the rest", "could be extracted") while another module still owns part of its format or protocol, or the same constant is defined on both sides.
  - Fix: either commit to the boundary (move the format into the package, and add a test that checks its imports), or drop the claim and the duplication that serves it. The halfway state costs some of each.
- **An entry-point layer that knows protocol details,** such as building HTTP URLs, SQL or shell commands in a CLI command or request handler. Push those details into the adapter.

## 5. Single responsibility

- **Count the jobs.** List what each module and class does, in plain words. Four jobs in one module (validation, naming, a file format, a history log) is the signal to split.
- **Duplicated records.** A file or table that repeats facts already held elsewhere. Keep each fact in one place.
- **An untyped bag that hides structure:** `**kwargs: Any`, `dict[str, Any]` passed around, or long parameter lists that shuttle the same values through several functions. Usually this shows a responsibility in the wrong place.

## 6. Ports and adapters, without naive renaming

- **A port should be cut where the domain needs substitution.** The test doubles show where that is:
  - If a fake **subclasses the real implementation** and overrides only some methods, the methods it doesn't override aren't really part of the port. Real filesystem calls running against a temporary directory are a common example. Move them out of the port.
  - If a fake has to **re-parse command strings, URLs or queries** with regexes to emulate a service, the port sits at the wrong level. Make it service-shaped (`create_invoice`, `list_invoices`), so the fake becomes a dictionary, and keep one small test of the real adapter.
- **A port that mixes concerns:** process control, filesystem access and pure computation in one interface. Keep pure computation (such as building a path or an identifier) out of ports altogether.
- **Don't rename for the pattern's sake.** Suffixes like `Port`, `Adapter` or `Impl` add jargon. Name the interface for what it represents (`Clock`, `Storage`, `PaymentGateway`) and the implementation for what it is (`SystemClock`, `S3Storage`).

## 7. DRY, within reason

- **Remove repetition that hides a single fact,** such as the same file name or URL defined in two modules, or the same fetch-normalise-compare sequence in two commands.
- **Leave repetition that is trivially easy to understand,** such as two five-line lookups with different error messages. Say explicitly that you're leaving it, so the omission doesn't look like an oversight.

## 8. Trivial helpers

- **Detect:** a function with one call site whose body is a line or two, and whose name adds nothing beyond its body. Count the call sites with a search.
- **Inline it.** Common cases:
  - private path or string builders used once;
  - accessors over a dict or map that would be fields on a typed record;
  - a private wrapper used by one public method;
  - a parameter whose default is never overridden.
- **A test that pins a helper is not a reason to keep it.** Tests that exist only to cover a helper with one caller are a sign it's tested as an interface without being one. Move those tests to the caller.

## 9. Over-defensive code

- **Validating files or data the program wrote itself,** field by field, sometimes raising exceptions purely to jump to an error handler. Replace it with a straightforward load that fails once, with a clear message naming the file: "not a … written by <tool> (missing key …)".
- **Defaulting and type checks on data whose shape the program controls,** such as `x.get(...) or []`, `isinstance` or null checks.
- **Checks that the inputs can't trigger,** because they are validated earlier or come from the user's own configuration.
- **Keep tolerance where the input is what's being checked.** For example, a malformed file that a validation command inspects should become a reported problem, not a crash.
- **Make error handling consistent.** One loader should produce clear "missing" and "invalid" messages for every file, rather than a friendly error for one file and a stack trace for its neighbour.

## 10. Control-flow smells

- **A callback or strategy with exactly two implementations,** one of them a no-op. Use a flag and an `if`.
- **Equality tested by building a diff or a report** and checking whether it's empty. Return a value whose absence means equal, for example `Difference | None`.
- **A result object that is mostly "nothing to report".** If most instances mean "ok", report only the problems: return a list of problems, where an empty list means success.
- **Cross-cutting arguments every handler must accept,** such as each CLI command or request handler receiving a parameter only one of them uses. Let the handler that needs it own it.

## 11. Stale text

- **Comments, docstrings and docs that name removed files, functions, flags or options.** Search for the old names after any removal.
- **Comments that state an invariant the structure no longer needs,** such as "must match the value in the file" when the value could simply be read from the file.

## 12. Dependencies and testability

- **Dependencies point the wrong way.** Domain code (rules, models, calculations) imports infrastructure (HTTP clients, database access, process or filesystem calls).
  - Detect: read each domain module's imports.
  - Fix: the domain defines the interface it needs, and the infrastructure implements it. A constant or type imported from an adapter into the domain usually belongs in the domain.
- **Wiring is scattered.** Global instances, singletons, or functions that construct their own clients.
  - Fix: build real implementations once, at the entry point (the composition root), and pass them in.
- **Validation is repeated inside the core.** Untrusted input is checked in many places instead of being converted into typed values once, at the boundary.
  - Fix: parse at the edge. Code past the boundary trusts its types.
- **Logic is tangled with I/O.** A function that fetches, decides and acts in one body.
  - Fix: split it so the decision is a pure function that is easy to test and move.
- **Import cycles,** or imports deferred inside functions to dodge them. These usually mean a boundary is in the wrong place. Give the shared concept its own module.
- **Tests are coupled to structure.** Mocks that patch internal import paths or private functions break on every rename or move, even when behaviour is unchanged.
  - Fix: flag them before a mechanical refactor. Prefer stubs and fakes passed in through interfaces, and testing through public entry points.
  - See `testing.md` for the full stance, the smells table and when patching is acceptable.
