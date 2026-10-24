# Testing: test doubles, injection, and why patching is a smell

Read this whenever the review covers tests, and before writing a brief that changes code under test.

The stance:
- **Components receive their dependencies** (clocks, storage, HTTP clients, process runners, message senders) through constructor or function parameters typed as interfaces.
- **Tests pass simple stand-ins** for those dependencies.
- **Replacing things by patching** module attributes or globals is a code smell in all but trivial cases. It signals a missing seam in the production code, not a testing technique to reach for.

## Contents

1. Vocabulary
2. What to prefer, in order
3. Why patching is a smell
4. When patching is fine
5. Keeping fakes honest
6. Shape of a healthy suite
7. Smells to report in a review
8. How test findings feed the proposal and the brief
9. Python

## 1. Vocabulary

These are Gerard Meszaros's terms, as popularised by Martin Fowler. Use them precisely in a review, since "mock" is often used loosely for all of them.

| Double | What it does | Typical use |
|---|---|---|
| **Dummy** | Fills a parameter; never used | Satisfying a signature |
| **Stub** | Returns canned answers to queries | "The clock says 9:00", "the API returns this ruleset" |
| **Fake** | A working, simplified implementation | An in-memory repository; a dictionary-backed service client |
| **Spy** | A stub or fake that also records what it received | Checking which emails were "sent" |
| **Mock** | Pre-programmed with expected calls, and fails the test if they don't happen | Verifying an interaction protocol, which is rarely what you want |

## 2. What to prefer, in order

1. **Real objects** when they are fast, deterministic and local: pure functions, value objects, a temporary directory on a real filesystem.
2. **Stubs** for queries: the test controls what the dependency answers.
3. **Fakes** when the code makes several related calls, such as a write followed by a read. One small fake beats a pile of per-test stub answers.
4. **Spies, or fakes that record,** for commands whose effect *is* the outbound side effect: sending, publishing, charging. Assert on what was recorded, such as "one email to X with subject Y", not on call order or exact arguments that don't matter.
5. **Mocks with interaction expectations,** only when the protocol itself is the requirement: "retry exactly three times, then give up". This is rare.

**Assert on outcomes rather than interactions.** Check the returned value, the resulting state, or the recorded effect. Tests that assert "method A was called with B" restate the implementation, and break on harmless refactors.

## 3. Why patching is a smell

Patching means replacing a name inside a module at test time: `mock.patch("app.billing.requests.post")`, `monkeypatch.setattr(app.billing, "now", ...)`, or swapping a global or singleton. It causes four problems:

- **It couples tests to import paths and internal names.** Moving or renaming a function breaks the tests even though behaviour is unchanged. That is exactly what a mechanical refactor does.
- **It hides dependencies.** A function's signature no longer says what it needs, so readers and callers can't see it.
- **It patches the wrong place easily.** You must patch where a name is *looked up*, not where it's defined. Tests pass or fail for reasons unrelated to behaviour.
- **It signals a missing seam.** If a test has to reach in and replace something, the production code should have accepted it as a parameter.

The fix belongs in the production code, not the test: add a parameter for the dependency, typed as an interface, with the real implementation supplied once at the entry point (the composition root). The test then constructs the component with a stub or fake.

## 4. When patching is fine

Treat these as trivial, acceptable cases:

- **Process environment and context at the very edge:** environment variables, the current directory, `argv`, a home directory, using the test framework's scoped helpers. This is acceptable only where the entry point reads them; deeper code should receive the values as parameters.
- **Testing the composition root or entry point itself,** where wiring real implementations is the behaviour under test.
- **A third-party library with no seam,** called from inside the one adapter that wraps it, in that adapter's own tests. The adapter is the seam for everything else.
- **Legacy code being brought under test** before a refactor (characterisation tests). Mark these tests as temporary, and list them in the brief as "replaced by injection in step N".

Anything else gets a finding: "patched dependency, suggest injecting `<interface>` into `<component>`".

## 5. Keeping fakes honest

A fake that drifts from the real implementation makes tests pass against behaviour production doesn't have.

- **Implement the interface, don't subclass the real class.** A fake that inherits from the real implementation silently runs real code for every method it doesn't override.
- **Let the type checker verify the fake** against the interface.
- **Keep fakes small:** just enough behaviour for the component's tests. A fake that grows its own logic needs tests of its own, or should be replaced by the real thing.
- **Write contract tests:** one set of tests about the interface, run against both the fake and the real adapter. The real one runs in a slower, marked integration suite (against a local server, a container or a sandbox account), and keeps the fake truthful.
- **Put one fake per interface in a shared test-support module,** rather than redefining ad-hoc stand-ins in each test file.
- **Make fakes speak the domain's language.** A fake that has to parse command strings, URLs or SQL to decide what to return shows the interface is at the wrong level (checklist 6). Make the interface service-shaped, and the fake becomes a dictionary.

## 6. Shape of a healthy suite

- **Most tests exercise the core** (domain logic and use cases) through its public functions or classes, with stubs and fakes for its interfaces. They are fast, deterministic and independent of module layout.
- **A few adapter tests** check each real adapter against the real thing, or a realistic stand-in, at the boundary: request shape, error mapping, parsing of real responses.
- **One or two end-to-end tests** prove the wiring at the composition root.
- **Tests target public behaviour.** A test that imports a private helper is a sign the helper is hiding an untested public responsibility, or that the test is pinning implementation details.

## 7. Smells to report in a review

| Smell | How to detect it | Suggested change |
|---|---|---|
| Patching module attributes or globals | Search the tests for `patch(`, `monkeypatch.setattr`, `jest.mock`, `sinon.stub(module`, or replaced globals; count them per test file | Inject the dependency; see section 3 |
| Patch targets that are internal import paths | String targets naming the module under test (`"app.billing.requests"`) | Same; list them as refactor-fragile meanwhile |
| Interaction assertions on queries | `assert_called_with` or `toHaveBeenCalledWith` on a dependency that only returns data | Assert on the result instead |
| Mocks returning mocks | Chains such as `client.return_value.get.return_value.json.return_value` | The interface is too low-level; introduce a service-shaped one |
| Mocks without a spec | Auto-generated mocks that accept any attribute | Use a spec or autospec, or better, a hand-written fake typed against the interface |
| Fakes that subclass the real class | The fake's base class is the production implementation | Implement the interface instead; move the methods it doesn't override out of the interface |
| Fakes keyed on command strings or URLs | Regexes or string parsing inside a fake | Make the interface service-shaped |
| Ad-hoc stand-ins repeated across files | Several tests each defining their own fake of the same thing | One shared fake per interface |
| Tests mirroring implementation steps | A test asserting each internal call in order | Assert on the outcome; keep the call order only when it is the requirement |
| Time, randomness or IDs read directly | `now()`, `random()` or `uuid4()` called inside the core, with tests patching them | Inject a clock, a random source or an ID generator |
| Tests of private functions | Imports of `_private` names | Test through the public entry point, or make the responsibility public in its own module |

## 8. How test findings feed the proposal and the brief

- **Moving from patching to injection changes signatures,** so it is a **structural** change, not a mechanical one. Put it in the structural step that follows the mechanical brief, unless the user decides otherwise.
- **A mechanical brief must still list** every patch target whose import path the brief changes, and require those tests to be updated in the same commit as the move. Otherwise the suite turns red, or passes while patching nothing.
- **When proposing injection,** name the interface, the component that receives it, the real implementation, and where it's wired (the composition root). Name the shared fake the tests will use.
- **Where coverage relies on patched characterisation tests,** keep them until the injection step lands, then replace them.

## 9. Python

**An interface, a fake, and injection:**

```python
class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:  # a stub: tests/fakes.py
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


class InvoiceService:
    def __init__(self, store: InvoiceStore, clock: Clock) -> None:
        self._store, self._clock = store, clock
```

Production wires `InvoiceService(PostgresInvoiceStore(...), SystemClock())` in `main()`. Tests build `InvoiceService(InMemoryInvoiceStore(), FixedClock(at))`.

- **Fakes are plain classes** that satisfy the `Protocol`. mypy or pyright checks them where they're passed. Optionally add `_: Clock = FixedClock(...)` in the fakes module to check eagerly.
- **pytest fixtures** construct components with their fakes. Fixtures that `monkeypatch` modules are the smell from section 3.
- **Fine to use:** `tmp_path` (a real filesystem, isolated), `monkeypatch.setenv`/`delenv` and `monkeypatch.chdir` at the entry point, `capsys` and `caplog`.
- **`unittest.mock`:** if a mock really is warranted (section 2, item 5), build it with `create_autospec(TheInterface, instance=True)` so that misspelled attributes and wrong signatures fail. Prefer a hand-written spy that records calls in a list: it reads better in assertions and survives refactors.
- **Time, randomness and IDs:** inject a `Clock`, a `random.Random` instance, or an ID factory such as `Callable[[], str]`, rather than patching `datetime`, `random` or `uuid`. Libraries like `freezegun` and `time-machine` are a form of patching; accept them only in legacy characterisation tests.
- **Subprocesses and HTTP:** wrap them in a service-shaped adapter, such as `payments.refund(order_id)` rather than `run(["curl", ...])` or raw `requests.post(...)`. Test the adapter alone, with a recorded response or a local server. Everything else uses the adapter's fake.
- **Search terms for counting the smell:** `mock.patch`, `@patch`, `patch.object`, `monkeypatch.setattr`, `MagicMock(`, `freezegun`.
