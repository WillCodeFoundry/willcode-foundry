# 5. Functions that do two jobs

A function whose name or signature hides that it does more than one thing, or whose callers must help it do its one thing.

## 5.1 Validate-and-fetch, lookups that write

A function that both checks and returns something, a lookup that also writes, or a call made only for its side effect.

Bad:

```python
def require_valid_order_args(shop: Shop, order_id: str, quantity: int) -> Customer:
    """The customer to bill, once the arguments check out."""
    Order.parse_id(order_id)  # called only to raise on a bad id
    if quantity < 1:
        raise ShopError("quantity must be at least 1")
    return shop.customer_for(order_id)
```

Better:

```python
def require_valid_order_args(order_id: str, quantity: int) -> None:
    if not Order.is_valid_id(order_id):
        raise ShopError(f"{order_id!r} is not an order id")
    if quantity < 1:
        raise ShopError("quantity must be at least 1")


customer = shop.customer_for(order_id)
```

- **Why:** the name has to say both jobs, or it lies about one. The check keeps its name once it returns nothing, since it now does only what the name says. Neither job can be reused alone, and a constructor called for its side effect looks like dead code.
- **Fine when:** the pair is atomic by nature, such as `dict.pop` or a compare-and-set.
- **Spot it:** names with "and"; a return value most callers ignore; a call whose result is discarded but whose comment says it "refuses" or "checks".

## 5.2 Flags that pick a behaviour

A boolean parameter that switches the function between two jobs.

Bad:

```python
def total(order: Order, include_tax: bool) -> Decimal:
    net = sum((line.price for line in order.lines), Decimal(0))
    if include_tax:
        return net * (1 + order.tax_rate)
    return net
```

Better:

```python
def net_total(order: Order) -> Decimal:
    return sum((line.price for line in order.lines), Decimal(0))


def gross_total(order: Order) -> Decimal:
    return net_total(order) * (1 + order.tax_rate)
```

- **Why:** every call site reads as `total(order, True)`, and each new flag doubles the paths to test.
- **Fine when:** the flag tunes one behaviour rather than choosing between two, such as `reverse=True` on a sort.
- **Spot it:** Ruff `FBT001`/`FBT002` flag boolean positional parameters, though not whether the flag splits the function.

## 5.3 Arguments the callee could derive

Callers pass a value that is a function of another argument they also pass.

Bad:

```python
zone = zone_for(order.postcode)
quote = courier.quote(order.postcode, zone)
```

Better:

```python
quote = courier.quote(order.postcode)  # quote() derives the zone itself
```

- **Why:** every caller must derive it the same way, and nothing stops the two arguments disagreeing.
- **Fine when:** deriving it is expensive and the caller already has it, and the callee checks they agree.
- **Spot it:** the same derivation repeated just before each call.

## 5.4 Signatures erased by `*args` and `**kwargs`

An override or wrapper that takes `*args, **kwargs` and passes them through.

Bad:

```python
class TrackedCourier(Courier):
    def quote(self, *args: object, **kwargs: object) -> Decimal:
        quote = super().quote(*args, **kwargs)  # type: ignore[arg-type]
        metrics.record("quote", quote)
        return quote
```

Better:

```python
class TrackedCourier(Courier):
    def quote(self, postcode: str) -> Decimal:
        quote = super().quote(postcode)
        metrics.record("quote", quote)
        return quote
```

- **Why:** callers lose the signature, and a change to the parent's parameters no longer shows up here. The `type: ignore` it needs is the tell.
- **Fine when:** it is a generic decorator that must wrap any callable, typed with `ParamSpec`.
- **Spot it:** `*args, **kwargs` in an override, especially beside an ignore comment.

## 5.5 Several results in a tuple

A function that returns a `tuple` of values with different meanings, which callers unpack by position.

Bad:

```python
def price_order(order: Order) -> tuple[Decimal, Decimal, list[str]]:
    net = sum((line.price for line in order.lines), Decimal(0))
    warnings = [f"{line.sku} is low on stock" for line in order.lines if line.stock < line.quantity]
    return net, net * order.tax_rate, warnings


net, tax, _ = price_order(order)
_, tax, _ = price_order(order)
```

Better:

```python
@dataclass(frozen=True)
class Price:
    net: Decimal
    tax: Decimal


def price_order(order: Order) -> Price:
    net = sum((line.price for line in order.lines), Decimal(0))
    return Price(net=net, tax=net * order.tax_rate)


def stock_warnings(order: Order) -> list[str]:
    return [f"{line.sku} is low on stock" for line in order.lines if line.stock < line.quantity]
```

- **Why:** two values of one type can swap at a call site and still pass mypy. A caller that needs one value names the rest `_`, and adding a value breaks every caller. Values of unrelated meaning, like the warnings here, usually mean two jobs.
- **Fine when:** the pair is one idea that the standard library also returns as a tuple, such as `divmod` or `str.partition`.
- **Spot it:** `-> tuple[` with two or more meanings; `_` in the unpacking at call sites.

## 5.6 Effects inside a calculation

A function that computes a value and also reads or writes the outside world: a file, a database, the network, the clock. A constructor that does I/O is the same smell.

Bad:

```python
def invoice_total(order_id: str, db: Database, mailer: Mailer) -> Decimal:
    order = db.load_order(order_id)
    total = sum((line.price * line.quantity for line in order.lines), Decimal(0))
    if total > REVIEW_LIMIT:
        mailer.send_review_request(order_id)
    db.save_total(order_id, total)
    return total


class PriceList:
    def __init__(self, path: Path) -> None:
        self.prices = {sku: Decimal(price) for sku, price in json.loads(path.read_text()).items()}
```

Better:

```python
def invoice_total(order: Order) -> Decimal:
    return sum((line.price * line.quantity for line in order.lines), Decimal(0))


def needs_review(total: Decimal) -> bool:
    return total > REVIEW_LIMIT


class PriceList:
    def __init__(self, prices: Mapping[str, Decimal]) -> None:
        self.prices = dict(prices)

    @classmethod
    def read(cls, path: Path) -> "PriceList":
        return cls({sku: Decimal(price) for sku, price in json.loads(path.read_text()).items()})
```

The caller loads the order, saves the total and sends the mail.

- **Why:** a test of the arithmetic must fake the database and the mailer. A failure halfway leaves some writes done. The rule can't be reused for a preview that must not write. A constructor that reads a file makes every test write one.
- **Fine when:** the function's job is to sequence effects, as an entry point or a composition root does; or the effect is the point, as in `save_total`.
- **Spot it:** a test of a calculation that needs fakes; a function that returns a computed value and also calls a `save`, `send` or `write`; `open(`, `read_text(` or a client call inside `__init__`.
