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

## 6.4 Going around the framework or the standard library

Re-implementing something the framework, a base class or the standard library already provides.

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

The standard library's versions are missed most often. Progress reported through a callback is a common case.

Bad:

```python
def import_catalogue(path: Path, report: Callable[[str], None] = lambda line: None) -> None:
    for row in read_rows(path):
        save_product(row)
        report(f"imported {row.sku}")


import_catalogue(path, report=print)  # in main
```

Better:

```python
_LOGGER = logging.getLogger(__name__)


def import_catalogue(path: Path) -> None:
    for row in read_rows(path):
        save_product(row)
        _LOGGER.info("imported %s", row.sku)
```

The entry point configures a handler once. Results stay return values; `logging` is for progress.

- **Why:** the local copy skips the framework's error handling and checks, and shared code grows special cases for it. A progress callback is threaded through every layer between the entry point and the work, and every test passes one. `logging` brings levels, one place to configure output, and pytest's `caplog`.
- **Fine when:** the framework's helper can't do what you need, and you say why next to the code.
- **Spot it:** before writing a helper, grep the base class and the framework docs for one that exists. A `report`, `echo` or `on_progress` parameter passed down several calls; `print` outside the entry point. Paired calls such as `start()` and `stop()` where a `contextlib.contextmanager` would keep them together; hand-made temporary dirs where `tempfile` fits.

## 6.5 Reading a format one way, writing it another

A file read with a real parser, then edited with a regex or string splicing that assumes its layout.

Bad:

```python
def supplier_of(listing: Path) -> str:
    return yaml.safe_load(listing.read_text())["supplier"]["name"]


def change_supplier(listing: Path, old: str, new: str) -> None:
    pattern = re.compile(rf"^  name: {re.escape(old)}$", flags=re.MULTILINE)  # assumes two-space indents
    listing.write_text(pattern.sub(f"  name: {new}", listing.read_text()))
```

Better:

```python
def change_supplier(listing: Path, new: str) -> None:
    data = yaml.safe_load(listing.read_text())
    data["supplier"]["name"] = new
    listing.write_text(yaml.safe_dump(data, sort_keys=False))
```

- **Why:** a file the reader accepts, with other indents or quotes, makes the writer miss or edit the wrong line.
- **Fine when:** the file must keep comments or text the parser drops. Then parse the edited text and check it holds the new value.
- **Spot it:** `yaml`, `json` or `tomllib` reading a file in one function, and `re` or `str.replace` editing it in another.

## 6.6 Rebuilding a place the code already names

A path worked out by hops from a nearby file, where an object already names the place.

Bad:

```python
def save_cover(book: Book, image: bytes) -> None:
    (book.manifest.parent.parent / "covers" / f"{book.isbn}.jpg").write_bytes(image)
```

Better:

```python
def save_cover(shop: Shop, book: Book, image: bytes) -> None:
    (shop.covers_dir / f"{book.isbn}.jpg").write_bytes(image)
```

- **Why:** the hops encode a layout only its owner should know, and they break silently when a folder moves.
- **Fine when:** nothing names the place yet, and this is its only use.
- **Spot it:** `.parent.parent`, `"../.."` or nested `os.path.dirname`. A path built from a sibling file's location.
