# 3. Hiding failure

Code that meets something unexpected and carries on as if it were fine. Design rule 6 in `ARCHITECTURE.md` is the foundry's rule against it: fail fast, with a message, and don't program defensively.

## 3.1 Repairing instead of failing

Clearing, replacing or defaulting whatever is in the way, or falling back to a different answer when the real one fails.

Bad:

```python
def save_receipt(path: Path, text: str) -> None:
    if path.is_symlink():
        path.unlink()  # replace the link with a real file
    path.write_text(text)


def shipping_cost(order: Order) -> Decimal:
    try:
        return courier_api.quote(order)
    except QuoteError:
        logger.warning("quote failed, using flat rate")
        return FLAT_RATE
```

Better:

```python
def save_receipt(path: Path, text: str) -> None:
    if path.is_symlink():
        raise ShopError(f"{path} is a link: receipts are written only to files")
    path.write_text(text)


def shipping_cost(order: Order) -> Decimal:
    return courier_api.quote(order)
```

- **Why:** the caller never learns that something was wrong. The flat rate is a different answer, and the deleted link may have pointed at someone's data.
- **Fine when:** the fallback is the documented contract and the caller asked for it, such as an explicit `default=` argument.
- **Spot it:** `unlink`, `rmtree`, `missing_ok=True` or `exist_ok=True` before a write; a `warning` log followed by a different return value.

## 3.2 Catching more than you can handle

A broad `except`, or a `try` or `suppress` block wider than the one call that can fail.

Bad:

```python
try:
    order = parse_order(payload)
    reserve_stock(order)
    send_confirmation(order)
except Exception:
    return None
```

Better:

```python
try:
    order = parse_order(payload)
except ValidationError as error:
    raise BadRequest(str(error)) from error
reserve_stock(order)
send_confirmation(order)
```

- **Why:** the broad handler also swallows typos, bugs and failures in steps nobody meant to protect.
- **Fine when:** it is a top-level entry point that logs and reports every failure, such as a worker loop.
- **Spot it:** Pylint `W0718` and Ruff `BLE001` flag `except Exception`. A `noqa` beside it is a reason to look harder. No tool flags a `try` that covers too many statements by default.

## 3.3 Reading errors by their text

Deciding what went wrong by searching an exception's message.

Bad:

```python
try:
    return insert_order(order_id, cart)
except IntegrityError as error:
    if "orders_pkey" in str(error):
        return existing_order(order_id)
    raise
```

Better:

```python
try:
    return insert_order(order_id, cart)
except UniqueViolation as error:  # psycopg reports the constraint in error.diag
    if error.diag.constraint_name == "orders_pkey":
        return existing_order(order_id)
    raise
```

- **Why:** messages change between versions and drivers, and a wrong guess at the text means the branch never runs.
- **Fine when:** the library offers nothing structured, and a test pins the real message.
- **Spot it:** `in str(error)` or a regex on `error.args` inside an `except`.

## 3.4 Placeholders in the value's own domain

A missing value written as a real-looking one: `"none"`, `""`, `-1`, `"None"`, or `True` where anyone can supply `True`.

Bad:

```python
NO_COURIER = "none"

assigned = courier_name or NO_COURIER
if assigned == requested:  # a courier really named "none" is refused
    raise ShopError(f"order is already with {requested}")
```

Better:

```python
if courier_name is not None and courier_name == requested:
    raise ShopError(f"order is already with {requested}")


_VERIFIED = object()  # a marker no caller can forge
```

- **Why:** the placeholder collides with real data, or leaks into output, such as `"type": "None"` in an API error.
- **Fine when:** a format outside your control defines the placeholder, and you translate it at the boundary.
- **Spot it:** a module constant set to `"none"`, `""` or `-1` and compared with user data; `str(None)` reaching output.
