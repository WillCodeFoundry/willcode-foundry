# 4. Rules in the wrong place

A rule enforced somewhere other than where the state it protects lives, or on only some of the paths to that state. Design rule 7 in `ARCHITECTURE.md` covers one case: a composition root only builds and passes, and decides nothing.

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
