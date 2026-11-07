# 4. Rules in the wrong place

A rule enforced somewhere other than where the state it protects lives, on only some of the paths to that state, or split across several places. Design rule 7 in `ARCHITECTURE.md` covers one case: a composition root only builds and passes, and decides nothing.

## 4.1 A rule decided at the edge

A domain rule checked in a command, a view or a request handler instead of in the domain object, often backed by an `assert` deeper down.

Bad:

```python
# cli.py
def refund_command(orders: Orders, order_id: str) -> None:
    order = orders.get(order_id)
    if order.status is Status.SHIPPED:
        raise ShopError("a shipped order can't be refunded: open a return")
    orders.refund(order)


# orders.py
def refund(self, order: Order) -> None:
    assert order.status is not Status.SHIPPED
    ...
```

Better:

```python
# orders.py
def refund(self, order_id: str) -> None:
    order = self.get(order_id)
    if order.status is Status.SHIPPED:
        raise ShopError("a shipped order can't be refunded: open a return")
    ...


# cli.py
def refund_command(orders: Orders, order_id: str) -> None:
    orders.refund(order_id)
```

- **Why:** every other caller must remember the rule, and the `assert` disappears under `python -O`.
- **Fine when:** the check is about the edge itself, such as argument syntax or permissions of the person calling.
- **Spot it:** an `if ... raise` in a command or handler about the object's state, followed by a call into the object. An `assert` that restates it.

## 4.2 Half-guards

A guard that names a property but enforces it on only part of the input or only some paths.

Bad:

```python
def write_export(root: Path, name: str, text: str) -> None:
    target = root / name
    if target.is_symlink():  # meant: never write outside root
        raise ShopError(f"{name} is a link")
    target.write_text(text)
```

Better:

```python
def write_export(root: Path, name: str, text: str) -> None:
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ShopError(f"{name} would be written outside {root}")
    target.write_text(text)
```

- **Why:** `../` in the name, or a linked parent folder, gets past the check, and the guard's name makes readers trust it.
- **Fine when:** the guard says plainly what it doesn't cover, and something else covers the rest.
- **Spot it:** a security or integrity check computed in one branch and not reused by a later loop or path; path checks that look at one component.

## 4.3 Checking one value, acting on another

A guard checks the data before a step, and the action uses the data after it.

Bad:

```python
def rename_title(path: Path, old: str, new: str) -> None:
    if path.read_text().count(old) != 1:
        raise ShopError(f"{path}: expected {old!r} once")
    merge_supplier_changes(path)  # may rewrite the line holding old
    path.write_text(path.read_text().replace(old, new))  # then replaces nothing, silently
```

Better:

```python
def rename_title(path: Path, old: str, new: str) -> None:
    merge_supplier_changes(path)
    text = path.read_text()
    if (count := text.count(old)) != 1:
        raise ShopError(f"{path}: expected {old!r} once after the merge, found {count}")
    path.write_text(text.replace(old, new))
```

- **Why:** the guard passes on data the action never sees. `str.replace` and `re.sub` return their input unchanged when nothing matches, so the miss is silent.
- **Fine when:** the check and the action read the same variable, with nothing between them that can change it.
- **Spot it:** the same file or field read twice with a step between. A `replace` or `re.sub` whose match count nobody checks.

## 4.4 One rule in two places

One piece of knowledge, such as a format and its inverse, or a file's name and its folder, split across functions or modules.

Bad:

```python
# covers.py
def cover_name(isbn: str) -> str:
    return f"cover-{isbn}.jpg"


# shelf.py
def save_cover(shop: Shop, isbn: str, image: bytes) -> None:
    (shop.root / "media" / "covers" / cover_name(isbn)).write_bytes(image)


# catalogue.py
def isbn_from_cover(file_name: str) -> str:
    return file_name.removeprefix("cover-").removesuffix(".jpg")
```

Better:

```python
# covers.py: the one place that knows how covers are stored
def cover_path(covers_dir: Path, isbn: str) -> Path:
    return covers_dir / f"cover-{isbn}.jpg"


def isbn_from_cover(path: Path) -> str:
    return path.stem.removeprefix("cover-")
```

- **Why:** change one half and the other still runs, now wrong.
- **Fine when:** the halves sit in layers that mustn't import each other, and a test round-trips them.
- **Spot it:** a format built in one module and parsed in another. A file's name decided in one function and its folder in another.
