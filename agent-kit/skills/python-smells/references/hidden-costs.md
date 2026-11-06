# 9. Hidden costs

Code whose cost doesn't show where it is called: work repeated on every call, or a call that stops everything else.

## 9.1 Rebuilt on every call

A constant, compiled pattern or validator built inside a function that runs often.

Bad:

```python
def is_valid_sku(sku: str) -> bool:
    pattern = re.compile(r"[A-Z]{3}-\d{5}")
    return pattern.fullmatch(sku) is not None


def parse_order(raw: bytes) -> Order:
    return TypeAdapter(Order).validate_json(raw)
```

Better:

```python
SKU = re.compile(r"[A-Z]{3}-\d{5}")
ORDER = TypeAdapter(Order)


def is_valid_sku(sku: str) -> bool:
    return SKU.fullmatch(sku) is not None


def parse_order(raw: bytes) -> Order:
    return ORDER.validate_json(raw)
```

- **Why:** the build cost is paid per call on a hot path. A module-level name also documents the policy and lets tests import it.
- **Fine when:** the function runs rarely, or the value depends on its arguments.
- **Spot it:** `re.compile`, `TypeAdapter(`, `frozenset({` or large literals inside a function body.

## 9.2 Blocking the event loop

A synchronous network, disk or sleep call inside an `async def`.

Bad:

```python
async def refund(order: Order) -> None:
    payments.refund(order.payment_id)  # a blocking HTTP call
    await notify(order.customer)
```

Better:

```python
async def refund(order: Order) -> None:
    await asyncio.to_thread(payments.refund, order.payment_id)
    await notify(order.customer)
```

- **Why:** every request on the loop waits for this one call. Code that wraps some calls and not others is the usual sign.
- **Fine when:** the call is known to return at once, such as an in-memory lookup.
- **Spot it:** Ruff's `ASYNC` rules catch `time.sleep` and some HTTP clients, but not an SDK's own blocking methods. Grep an async module for calls without `await`.
