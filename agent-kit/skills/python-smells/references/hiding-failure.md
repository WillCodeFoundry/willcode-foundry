# 3. Hiding failure

Code that meets something unexpected and carries on as if it were fine, or tells its caller the wrong thing about what happened. Design rule 6 in `ARCHITECTURE.md` is the foundry's rule against it: fail fast, with a message, and don't program defensively.

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

## 3.5 Losing which outcome happened

A function with several outcomes returns a `bool`, or returns some failures and raises others. The caller then has to work out what happened.

Bad:

```python
def import_catalogue(feed: Feed) -> bool:
    """False if the feed was rejected or only partly imported."""
    ...


if not import_catalogue(feed):
    if catalogue.count_from(feed.supplier) == 0:  # guess which False it was
        raise ShopError(f"{feed.supplier}'s feed was rejected")
    warn(f"{feed.supplier}'s feed was only partly imported")
```

Better:

```python
class Imported(Enum):
    ALL = "all"
    PARTLY = "partly"


def import_catalogue(feed: Feed) -> Imported:
    """Raises FeedRejected when nothing could be imported."""
    ...
```

- **Why:** the guess reads state that something else may have changed, and every caller repeats it. A failure returned as a value is easy to drop when the others raise.
- **Fine when:** there are really two outcomes, and `False` names one of them.
- **Spot it:** a `bool` or `Literal` return where one value means "failed", beside `raise` for other failures. A caller that queries state straight after a call to learn what it did.

## 3.6 Errors that name the wrong cause

Checks folded into one expression, or a value set only to trip a later check, so the message reports a different problem from the real one.

Bad:

```python
def read_price(row: object) -> Price:
    fields = row.get("price") if isinstance(row, dict) else None  # None only to fail below
    missing = [key for key in ("amount", "currency") if not (isinstance(fields, dict) and fields.get(key))]
    if missing:
        raise ShopError(f"price has no {', '.join(missing)}")  # "price": "9.99" reports both as missing
    ...
```

Better:

```python
def read_price(row: object) -> Price:
    if not isinstance(row, dict) or not isinstance(fields := row.get("price"), dict):
        raise ShopError(f"a row's price should be a mapping of amount and currency: {row!r}")
    if missing := [key for key in ("amount", "currency") if not fields.get(key)]:
        raise ShopError(f"price has no {', '.join(missing)}")
    ...
```

- **Why:** the reader goes looking for a field that is there, so the message sends them the wrong way.
- **Fine when:** the causes share one fix, so one message serves them all.
- **Spot it:** a type check repeated inside each field check. A variable set to `None` or `{}` only so the next check fails.

## 3.7 Raising after the writes

A function that writes as it goes, collects failures, and raises at the end. The exception says nothing happened, though most of it did.

Bad:

```python
def restock(deliveries: list[Delivery]) -> None:
    failed = []
    for delivery in deliveries:
        try:
            stock.add(delivery)  # written at once
        except StockError as error:
            failed.append(f"{delivery.id}: {error}")
    if failed:
        raise ShopError("restock failed:\n" + "\n".join(failed))  # the others were added
```

Better:

```python
@dataclass(frozen=True)
class Restocked:
    added: list[Delivery]
    failed: list[tuple[Delivery, str]]


def restock(deliveries: list[Delivery]) -> Restocked:
    """Add every delivery that can be added; the result says which couldn't."""
    ...
```

- **Why:** a caller that catches the error believes nothing changed, and a retry adds the deliveries twice.
- **Fine when:** the writes are rolled back before raising, or every check runs before the first write.
- **Spot it:** a loop that writes and appends to a `failed` list, followed by `raise`. An error that lists what failed and not what was written.

## 3.8 Raising away from the check

A function that finds the problem but leaves the raise to someone else. It returns a reason for its caller to raise, or it builds an exception for another function to raise.

Bad:

```python
def stock_problem(item: Item, quantity: int) -> str | None:
    """Why the item can't be reserved, or None when it can."""
    if item.discontinued:
        return "it is discontinued"
    if item.stock < quantity:
        return f"only {item.stock} left"
    return None


def reservation_error(sku: str, reason: str) -> ShopError:
    return ShopError(f"can't reserve {sku}: {reason}")


if reason := stock_problem(item, quantity):
    raise reservation_error(item.sku, reason)
```

Better:

```python
def require_in_stock(item: Item, quantity: int) -> None:
    if item.discontinued:
        raise ShopError(f"can't reserve {item.sku}: it is discontinued")
    if item.stock < quantity:
        raise ShopError(f"can't reserve {item.sku}: only {item.stock} left")


require_in_stock(item, quantity)
```

- **Why:** every caller must remember to raise, and one that forgets fails silently. The traceback points at the caller, not at the check that found the problem. A reader of the check can't see that it ends in an error.
- **Fine when:** the reasons are a result in their own right, such as a list of form errors shown to the user, and no caller raises them. Or when one function works out a long message's reason and raises once, at its end, rather than repeating the message.
- **Spot it:** a function returning `str | None` whose every caller raises on a `str`. A function that returns an exception instance. `raise make_error(...)`, or `raise` of a helper's result.
