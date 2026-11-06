# 1. Building for nobody

Code written for a caller, a requirement or a case that doesn't exist. It reads as load-bearing, so others maintain, test and copy it. Design rule 6 in `ARCHITECTURE.md` says the same of failures: handle only what has happened or what the design expects.

## 1.1 Code nobody calls

A helper, class, method, attribute or message field that nothing reads. Common forms: one lookup per enum value, a null object, a sync twin of an async function, a compatibility shim with no in-tree caller, and a stub "kept for symmetry".

Bad:

```python
class OrderRepository:
    def by_id(self, order_id: str) -> Order: ...
    def by_customer(self, customer_id: str) -> list[Order]: ...
    def by_courier(self, courier_id: str) -> list[Order]: ...  # no caller
    def by_postcode(self, postcode: str) -> list[Order]: ...  # no caller


class NullOrderRepository(OrderRepository):  # nothing constructs it
    ...
```

Better:

```python
class OrderRepository:
    def by_id(self, order_id: str) -> Order: ...
    def by_customer(self, customer_id: str) -> list[Order]: ...
```

- **Why:** each unused method is an API to keep working, document and test, and the next author copies the pattern.
- **Fine when:** it is a public library API with a deprecation date, or the task's spec asks for it.
- **Spot it:** `git grep -n -w <name>` finds only the definition. vulture lists unused definitions across a package. Docstrings that say "kept for", "for symmetry" or "never called" are a giveaway.

## 1.2 Parameters nobody varies

A parameter the body ignores, or one every caller passes the same way.

Bad:

```python
def ship(order: Order, courier: Courier, express: bool = False, region: str | None = None) -> Label:
    return courier.label_for(order)  # express and region are never read
```

Better:

```python
def ship(order: Order, courier: Courier) -> Label:
    return courier.label_for(order)
```

- **Why:** callers compute and pass values for nothing, and readers assume a dependency that isn't there. Copied into a template, the parameter spreads to every descendant.
- **Fine when:** the signature must match a protocol or callback type you don't own.
- **Spot it:** Ruff `ARG001`/`ARG002` and Pylint `W0613` flag a parameter the body ignores. They miss one every caller passes the same way: grep the call sites.

## 1.3 Behaviour nobody asked for

Live code for an edge case or a fidelity no user needs, such as preserving bytes, encodings or orderings the data never has.

Bad:

```python
def read_notes(path: Path) -> str:
    """The notes exactly as stored: CRLF kept, invalid UTF-8 kept, so writing them back changes nothing."""
    with path.open(encoding="utf-8", errors="surrogateescape", newline="") as notes:
        return notes.read()
```

Better:

```python
def read_notes(path: Path) -> str:
    """The notes, which the shop only ever writes as UTF-8 with LF line endings."""
    return path.read_text(encoding="utf-8")
```

- **Why:** the extra requirement shapes every function that touches the data, and later code grows to serve it.
- **Fine when:** a real input has the case, or the spec names it.
- **Spot it:** ask who produces the input this branch handles. If the answer is "nobody yet", delete the branch.

## 1.4 Wrappers that only rename

A function or class whose whole body forwards to one other call.

Bad:

```python
class StockChecker:
    def is_in_stock(self, sku: str) -> bool:
        return stock_level(sku) > 0


def check_stock(sku: str) -> bool:
    return StockChecker().is_in_stock(sku)
```

Better:

```python
def is_in_stock(sku: str) -> bool:
    return stock_level(sku) > 0
```

- **Why:** each extra name is one more thing to look up, and a stateless class built per call suggests a hierarchy that doesn't exist.
- **Fine when:** the wrapper adds a contract: validation, caching, a narrower type, or a seam the tests fake.
- **Spot it:** Ruff `PLR6301` and Pylint `R0903` flag a one-method class with no state. A function wrapper has no rule: read the body.

## 1.5 Interfaces that force stubs

A base class or `Protocol` that requires methods most implementers don't need, so each writes an empty one.

Bad:

```python
class Courier(Protocol):
    def label_for(self, order: Order) -> Label: ...
    def track(self, label: Label) -> Status: ...
    def cancel(self, label: Label) -> None: ...  # most couriers can't cancel


class LocalCourier:
    def cancel(self, label: Label) -> None:
        pass
```

Better:

```python
class Courier(Protocol):
    def label_for(self, order: Order) -> Label: ...
    def track(self, label: Label) -> Status: ...


class Cancellable(Protocol):
    def cancel(self, label: Label) -> None: ...
```

- **Why:** stubs hide which implementers really support a capability, so callers can't tell a cancel that works from one that does nothing.
- **Fine when:** the base class gives a real default that most implementers want.
- **Spot it:** several implementations of one method are `pass`, `return None` or `raise NotImplementedError`.
