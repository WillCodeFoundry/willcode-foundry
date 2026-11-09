# 10. Tests that prove nothing

Tests that pass whether or not the behaviour they name works. `CONTRIBUTING.md` sets the foundry's own test rules: each behaviour is tested once, at the cheapest tier, and tests never patch.

## 10.1 Expected values from the code under test

The test computes its expected value with the same formula or data the code uses.

Bad:

```python
def test_total_includes_tax() -> None:
    order = make_order(prices=[Decimal("10.00"), Decimal("5.00")])
    expected = sum(line.price for line in order.lines) * (1 + TAX_RATE)
    assert gross_total(order) == expected
```

Better:

```python
def test_total_includes_tax() -> None:
    order = make_order(prices=[Decimal("10.00"), Decimal("5.00")], tax_rate=Decimal("0.20"))
    assert gross_total(order) == Decimal("18.00")
```

- **Why:** if the formula is wrong, the test is wrong the same way and still passes.
- **Fine when:** the test compares two independent implementations, such as a fast path against a slow reference.
- **Spot it:** the code's own constants or helpers on the expected side of an assert.

## 10.2 Mocking the outcome

The test replaces the step whose effect it should check, then asserts the mock was called.

Bad:

```python
def test_failed_payment_cancels_order(shop: Shop) -> None:
    with patch.object(shop, "cancel") as cancel:
        shop.handle(PaymentFailed(order_id="A1"))
    cancel.assert_called_once_with("A1")
```

Better:

```python
def test_failed_payment_cancels_order(shop: Shop) -> None:
    shop.handle(PaymentFailed(order_id="A1"))
    assert shop.orders.get("A1").status is Status.CANCELLED
```

- **Why:** it proves a call happened, not that cancelling works, and it breaks on any refactor of how the call is made.
- **Fine when:** the mock stands in for an outside system at its boundary, such as a payment provider.
- **Spot it:** `patch.object` on the object under test; `assert_called` as the test's only assertion.

## 10.3 The edge case never happens

A regression test whose setup doesn't produce the case it is named for, so it passes without exercising it.

Bad:

```python
def test_last_item_cannot_be_oversold(stock: Stock) -> None:
    stock.add("ABC-00001", quantity=5)
    stock.reserve("ABC-00001", quantity=1)  # 4 left: never the last item
    assert stock.on_hand("ABC-00001") == 4
```

Better:

```python
def test_last_item_cannot_be_oversold(stock: Stock) -> None:
    stock.add("ABC-00001", quantity=1)
    stock.reserve("ABC-00001", quantity=1)
    with pytest.raises(StockError):
        stock.reserve("ABC-00001", quantity=1)
```

- **Why:** the name promises protection the test doesn't give, so the bug can return unnoticed.
- **Fine when:** never: a test should assert that its edge case happened.
- **Spot it:** break the code on purpose and run the test. mutmut automates this.

## 10.4 Faking the environment to test order

A stand-in executable, clock or file system built only to prove that one step ran before another.

Bad:

```python
def test_address_checked_before_courier_called(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called = tmp_path / "called"
    fake = tmp_path / "bin" / "courier-cli"
    fake.parent.mkdir()
    fake.write_text(f"#!/bin/sh\ntouch {called}\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake.parent}:{os.environ['PATH']}")
    with pytest.raises(ShopError):
        ship(order_with_bad_address())
    assert not called.exists()
```

Better:

```python
def test_bad_address_is_refused_and_nothing_ships(shop: Shop) -> None:
    with pytest.raises(ShopError, match="address"):
        shop.ship(order_with_bad_address())
    assert shop.shipments() == []
```

- **Why:** the test pins the implementation's sequence and adds machinery to maintain, while the observable result says the same thing.
- **Fine when:** the order is itself the requirement, such as a security check that must run before any outside call. The foundry's design rule 3 allows stand-ins on `PATH` for outside systems.
- **Spot it:** a helper that writes an executable or patches a clock, used by one test.

## 10.5 The same behaviour tested twice

A new test, or a new case in a parametrized test, that fails only when an existing test fails too. It often appears when a function reaches a rule only through another function, and the rule's test is copied to the caller.

Bad:

```python
def test_cancel_refuses_a_shipped_order(shop: Shop) -> None:
    with pytest.raises(ShopError, match="shipped"):
        shop.cancel(shipped_order().id)


def test_refund_refuses_a_shipped_order(shop: Shop) -> None:  # refund cancels first, so cancel's test already fails
    with pytest.raises(ShopError, match="shipped"):
        shop.refund(shipped_order().id)
```

Better: keep the first test, and test only what `refund` adds.

```python
def test_refund_returns_the_payment(shop: Shop) -> None:
    order = paid_order()
    shop.refund(order.id)
    assert shop.payments(order.id) == [order.total, -order.total]
```

- **Why:** a second test of one behaviour costs a run and an edit on every change to it, and protects nothing the first doesn't.
- **Fine when:** the caller can reach the rule some other way than through the function already tested.
- **Spot it:** for each new test, name the change to the code that would make it fail. If an existing test fails on the same change, one of them is redundant.

## 10.6 A parametrized test that asks which case it is

The shared body of a parametrized test branches or computes its expectation from one parameter's value, rather than taking the expectation as a parameter.

Bad:

```python
@pytest.mark.parametrize("order_id", ["paid-1", "shipped-1", "cancelled-1"])
def test_refund_refusals(shop: Shop, order_id: str) -> None:
    with pytest.raises(ShopError) as raised:
        shop.refund(order_id)
    assert isinstance(raised.value, ShippedError) == (order_id == "shipped-1")
```

Better:

```python
@pytest.mark.parametrize(
    ("order_id", "error"),
    [("paid-1", ShopError), ("shipped-1", ShippedError), ("cancelled-1", ShopError)],
)
def test_refund_refusals(shop: Shop, order_id: str, error: type[ShopError]) -> None:
    with pytest.raises(error):
        shop.refund(order_id)
```

- **Why:** a case added under another id silently takes the wrong branch, and the test still passes.
- **Spot it:** a parameter's literal value, or an `if` on a parameter, inside a parametrized test's body.

