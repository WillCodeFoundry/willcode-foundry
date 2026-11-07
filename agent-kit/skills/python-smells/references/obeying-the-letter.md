# 11. Obeying the letter of a rule

Code reshaped to satisfy a checker, a budget or a review request, and made worse by it. Every case here was a "cleanup" that a later reader had to undo or work around.

## 11.1 Rewrites that satisfy a checker

A clear loop or statement turned into something harder to read because a rule, such as "no mutable locals" or a lint budget, flagged the clear form.

Bad:

```python
# a rule against mutable locals turned an early-exit loop into a fold
def first_unpaid(orders: Sequence[Order]) -> Order | None:
    return reduce(lambda found, order: found or (order if not order.paid else None), orders, None)


# and a side-effecting call into a comprehension's filter
failed = tuple(order.id for order in batch if not send_invoice(order))
```

Better:

```python
def first_unpaid(orders: Sequence[Order]) -> Order | None:
    for order in orders:
        if not order.paid:
            return order
    return None


failed = []
for order in batch:
    if not send_invoice(order):
        failed.append(order.id)
```

- **Why:** the fold visits every order after it has found one. A comprehension reads as a pure transformation, so a send hidden in its filter surprises the reader.
- **Fine when:** the rewrite is at least as clear as the original. A local list that never escapes is not shared mutable state.
- **Spot it:** `reduce`, nested conditional expressions or `*()` splats replacing a short loop; a comment that justifies code by citing a budget or rule id.

## 11.2 Adding what a review asked for, unexamined

A guard, fallback, helper or test added only because a reviewer asked for it.

Bad:

```python
# review: "what if quantity is None?"  (the type says int, and every caller passes one)
def reserve(sku: str, quantity: int) -> None:
    if quantity is None:
        quantity = 1
    ...
```

Better:

```python
def reserve(
    sku: str, quantity: int
) -> None: ...  # answered in the review: quantity is an int at every call site, so no guard
```

- **Why:** a review request is not a requirement. Code added to close a comment is held to a lower bar than code written for the spec, and it is just as hard to remove.
- **Fine when:** the request names a real input or failure that happens, and you can show it.
- **Spot it:** before adding, ask the same questions as for your own code: families 1, 2 and 10.
