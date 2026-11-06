# 8. Narrating instead of naming

Comments and docstrings that repeat the code, describe who calls it, retell how it came to be, or promise what it doesn't do. The foundry's `AGENTS.md` asks the opposite: name the module or file instead of retelling what it does.

## 8.1 Comments that restate the code

A comment that says what the next line does, or a banner that splits a long function into sections.

Bad:

```python
# Get the order from the repository
order = orders.get(order_id)

### PRICING ###
# Loop over the lines and add up the prices
total = sum((line.price for line in order.lines), Decimal(0))
```

Better:

```python
order = orders.get(order_id)
total = order_total(order)  # what the banner marked is now a named function
```

- **Why:** the comment doubles what a reader must keep true, and it drifts until it is wrong. A banner marks a function that wants splitting.
- **Fine when:** the comment says why, or warns about something the code can't show, such as a vendor bug.
- **Spot it:** read each comment as a question: does the code beside it already answer it? No linter flags it; Ruff `E266` notices only `###` banners.

## 8.2 Docs about callers, history and plans

A docstring that describes who calls the function, what used to be broken, another function's errors, or the plan the code was written from.

Bad:

```python
def reserve(sku: str, quantity: int) -> None:
    """``_reserve_locked`` for the call sites that already hold the stock lock.

    Before #412 this scanned every warehouse, which double-counted transfers.
    Implements step 3b of docs/plans/stock-v2.md. Raises whatever checkout's validation raises.
    """
```

Better:

```python
def reserve(sku: str, quantity: int) -> None:
    """Hold ``quantity`` of ``sku`` for an order. Call it with the stock lock held.

    StockError when fewer than ``quantity`` are on hand.
    """
```

- **Why:** callers, history and plans change without anyone editing the docstring. The bug story belongs in the commit message and its test.
- **Fine when:** the history explains a choice that looks wrong but isn't, in one sentence that names the constraint.
- **Spot it:** docstrings that name other private functions, issue numbers, plan steps, or "for the call sites that".

## 8.3 Docs that promise what the code doesn't keep

A docstring or comment states an invariant that the body, or something it calls, breaks.

Bad:

```python
@dataclass(frozen=True)
class Refund:
    """Everything a refund needs, checked: issuing it can't fail before money moves."""

    order: Order
    amount: Money


def issue(refund: Refund) -> None:
    card = payments.fetch_card(refund.order)  # a network read that can fail first
    payments.send(card, refund.amount)
```

Better:

```python
@dataclass(frozen=True)
class Refund:
    """Everything a refund needs, checked: issuing it can't fail before money moves."""

    order: Order
    amount: Money
    card: Card  # fetched when the refund is made


def issue(refund: Refund) -> None:
    payments.send(refund.card, refund.amount)
```

- **Why:** readers trust the stated invariant and stop checking, so the doc hides the very case it rules out.
- **Fine when:** never. Change the code or the sentence.
- **Spot it:** docstrings that say "never", "always", "only", "can't" or "nothing". Check each against the body and the functions it calls.
