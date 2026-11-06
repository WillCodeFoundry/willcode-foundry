# 6. Copying instead of finding the seam

New code made by copying nearby code, or by going around a helper or base class that already does the job. Design rule 1 in `ARCHITECTURE.md` asks for one spelling per shared name, and copies are how that rule breaks.

## 6.1 Copied methods and near-twins

The same method pasted into sibling classes, or two functions that differ in one value.

Bad:

```python
class ParcelCourier:
    def wait_for_pickup(self, label: Label) -> None:
        while self.status(label) is not Status.COLLECTED:
            time.sleep(POLL_SECONDS)


class FreightCourier:
    def wait_for_pickup(self, label: Label) -> None:  # the same five lines
        while self.status(label) is not Status.COLLECTED:
            time.sleep(POLL_SECONDS)
```

Better:

```python
class PolledCourier:
    def wait_for_pickup(self, label: Label) -> None:
        while self.status(label) is not Status.COLLECTED:
            time.sleep(POLL_SECONDS)


class ParcelCourier(PolledCourier): ...


class FreightCourier(PolledCourier): ...
```

- **Why:** a fix to one copy misses the others, and the copies drift.
- **Fine when:** the copies are expected to diverge soon, and a comment says so; or there are only two and they are tiny.
- **Spot it:** Pylint `R0801` finds duplicate lines across files when run on the whole package. Within one file, read the siblings.

## 6.2 Repeated expressions and tables

The same expression, lookup table or reach into another object's internals, written out again at each use.

Bad:

```python
skus = tuple(s.strip() for s in (raw_skus or "").split(",") if s.strip())
tags = tuple(t.strip() for t in (raw_tags or "").split(",") if t.strip())
open_count = len([o for o in shop._store._orders.values() if o.status is Status.OPEN])
```

Better:

```python
def csv_values(raw: str | None) -> tuple[str, ...]:
    return tuple(value.strip() for value in (raw or "").split(",") if value.strip())


skus, tags = csv_values(raw_skus), csv_values(raw_tags)
open_count = shop.count_orders(Status.OPEN)
```

- **Why:** readers must diff the copies by eye, and a change to the internals breaks every caller that reached in.
- **Fine when:** two uses, both trivial, in one function.
- **Spot it:** the third copy of an expression; `obj._private` reached from another module, which Ruff `SLF001` flags.

## 6.3 Parallel implementations

Two implementations of one behaviour, such as a sync and an async path, or two transports, that every change must edit in step.

Bad:

```python
def place_order(cart: Cart) -> Order: ...  # 80 lines: validate, price, reserve, record


async def place_order_async(cart: Cart) -> Order: ...  # the same 80 lines with awaits, already slightly different
```

Better:

```python
def plan_order(cart: Cart) -> OrderPlan:  # the decisions, no I/O
    ...


def place_order(cart: Cart) -> Order:
    return store.record(plan_order(cart))


async def place_order_async(cart: Cart) -> Order:
    return await async_store.record(plan_order(cart))
```

- **Why:** each behaviour change is made twice, slightly differently, so the paths drift apart.
- **Fine when:** the two really behave differently, and the shared part is too small to extract.
- **Spot it:** a commit that makes the same edit in two files; function pairs named `x` and `x_async` or `ax`.

## 6.4 Going around the framework

Re-implementing something the framework or a base class already provides.

Bad:

```python
class ShopApp(App):
    def current_customer(self) -> Customer:
        token = self.request.headers["Authorization"].removeprefix("Bearer ")
        return Customer.from_token(token)
```

Better:

```python
class ShopApp(App):
    def current_customer(self) -> Customer:
        return self.authenticated_user()  # the framework's helper: one way to read the session
```

- **Why:** the local copy skips the framework's error handling and checks, and shared code grows special cases for it.
- **Fine when:** the framework's helper can't do what you need, and you say why next to the code.
- **Spot it:** before writing a helper, grep the base class and the framework docs for one that exists.
