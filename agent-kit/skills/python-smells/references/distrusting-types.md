# 2. Distrusting your own types

Code that re-checks, widens or overrides what a declared type already guarantees. It hides real type errors from the checker, and it tells the reader the shape is unknown when it isn't.

## 2.1 Defensive reads of declared fields

`getattr` with a default, `hasattr`, or an `isinstance` check on an attribute the class declares. A lookup by a name built from a string is the same smell.

Bad:

```python
def invoice_total(order: Order) -> Decimal:
    lines = getattr(order, "lines", None) or []
    discount = getattr(order, "discount", Decimal(0))
    return sum((line.price for line in lines), Decimal(0)) - discount


def handler_for(self, event: Event) -> Handler:
    return getattr(self, f"on_{event.value}", lambda *_: None)
```

Better:

```python
def invoice_total(order: Order) -> Decimal:
    return sum((line.price for line in order.lines), Decimal(0)) - order.discount


def handler_for(self, event: Event) -> Handler:
    match event:
        case Event.PAID:
            return self.on_paid
        case Event.SHIPPED:
            return self.on_shipped
```

- **Why:** if `Order` renames `discount`, the default hides it and every invoice is quietly wrong. A handler looked up by a built name returns a no-op for a new event instead of failing.
- **Fine when:** the object really is of unknown type, such as a third-party payload, and you validate it next.
- **Spot it:** `getattr(` with a literal name and a default, on a value with a declared type. No linter flags it, and mypy is silent too.

## 2.2 Types wider than the truth

`object`, `Any`, `str` or `| None` where the real type is narrower: a known enum, a literal set, or a value that is never `None`.

Bad:

```python
class Shipment(BaseModel):
    status: str  # one of the Status enum's values


def find_order(order_id: str) -> Order | None:
    return orders[order_id]  # raises KeyError; never returns None


order = find_order(order_id)
if order is None:  # can't happen
    raise NotFound(order_id)
```

Better:

```python
class Shipment(BaseModel):
    status: Status


def find_order(order_id: str) -> Order:
    return orders[order_id]
```

- **Why:** a wide type moves the checking to every consumer, and an optional that never happens grows dead branches at each caller.
- **Fine when:** the value really can be absent or of several types, and callers must handle each.
- **Spot it:** a return type with `| None` whose body has no `return None`. mypy `--strict` doesn't flag a redundant `is None` check, even with `--warn-unreachable`.

## 2.3 Casting instead of validating

`cast()`, or a `# type: ignore` with a comment arguing it's safe, on data from outside the program.

Bad:

```python
prices = cast(dict[str, Decimal], json.loads(response.text))  # the price feed always sends a dict
```

Better:

```python
PRICES = TypeAdapter(dict[str, Decimal])
prices = PRICES.validate_json(response.text)
```

- **Why:** the cast asserts a shape nobody checked, so bad input fails deep inside pricing code instead of at the boundary.
- **Fine when:** the value comes from your own code and the checker can't follow it, such as after a narrowing it doesn't understand.
- **Spot it:** `cast(` or `type: ignore` next to a comment that explains why the data is fine.

## 2.4 One parameter, several shapes

A parameter typed as a dict or an object, or a str or a list, so every read inside needs a branch.

Bad:

```python
def apply_discount(order: Order, options: dict[str, Any] | DiscountOptions) -> Decimal:
    rate = options.get("rate") if isinstance(options, dict) else options.rate
    cap = options.get("cap") if isinstance(options, dict) else getattr(options, "cap", None)
    ...
```

Better:

```python
def apply_discount(order: Order, options: DiscountOptions) -> Decimal: ...


# at the boundary, once:
options = DiscountOptions.model_validate(request.json())
```

- **Why:** every read handles both shapes, and a cleanup that assumes one shape breaks callers passing the other.
- **Fine when:** it is a public entry point that accepts both and converts at once.
- **Spot it:** `isinstance(x, dict)` paired with attribute access on the same parameter.
