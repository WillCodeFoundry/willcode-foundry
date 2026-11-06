# 7. Growing by accretion

Code that gets worse a little with each change, until no single diff looks wrong but the whole is hard to read or test. Judge these by the function or module whole, never by the hunk.

## 7.1 Functions every feature edits

A function or module that grows a branch for each feature, with a long parameter list that is a context object nobody named.

Bad:

```python
def checkout(
    cart, customer, coupon, gift_wrap, express, store_credit, loyalty, region, currency, notes
): ...  # 600 lines: pricing, stock, payment, loyalty and email, in one body
```

Better:

```python
@dataclass(frozen=True)
class Checkout:
    cart: Cart
    customer: Customer
    options: CheckoutOptions


def checkout(request: Checkout) -> Order:
    priced = price(request)
    reserve(priced)
    return charge(priced)
```

- **Why:** every change conflicts in one place, no step can be tested alone, and a regression bisects to unrelated work.
- **Fine when:** the function is long but flat and linear, such as a table of registrations.
- **Spot it:** Ruff `C901`, `PLR0912`, `PLR0913` and `PLR0915`, and Pylint `R0912` to `R0915`, catch the size. Check how many commits touched the function this month: `git log --since=1.month -L :checkout:shop/checkout.py`.

## 7.2 A special case per bug

Each fix adds a branch for the reported input, instead of correcting the rule that let it through.

Bad:

```python
def postage(order: Order) -> Decimal:
    if order.country == "GB" and order.weight < 2:
        return Decimal("3.50")
    if order.country == "GB" and order.weight == 2:  # fix for #812
        return Decimal("3.50")
    if order.country == "IE" and order.is_gift:  # fix for #840
        return Decimal("6.00")
    ...
```

Better:

```python
def postage(order: Order) -> Decimal:
    band = POSTAGE_BANDS[order.country]
    return band.price_for(order.weight)  # a gift no longer changes the band: the spec was wrong
```

- **Why:** each branch is a patch on the symptom, and the next bug lands between two of them.
- **Fine when:** the case really is special, the spec says so, and a test names it.
- **Spot it:** the third fix to the same function within a month. Stop and question the rule.

## 7.3 Global switches

A new environment variable or module-level flag for each experiment, read deep inside the code.

Bad:

```python
if os.environ.get("SHOP_ROUND_PRICES_UP") == "1":
    price = price.quantize(Decimal("1"), rounding=ROUND_UP)
```

Better:

```python
@dataclass(frozen=True)
class PricingOptions:
    round_up: bool = False


def final_price(price: Decimal, options: PricingOptions) -> Decimal: ...
```

- **Why:** any function can change behaviour without its signature saying so, and tests must patch the environment.
- **Fine when:** the variable wires a deployment, such as a URL or a secret, read once at startup.
- **Spot it:** `os.environ` or a settings singleton read outside the entry point.

## 7.4 One name, several meanings

A variable reassigned to mean something different partway through a function.

Bad:

```python
available = stock.on_hand(sku)
available = available - stock.reserved(sku)
available = max(available - safety_margin, 0)
```

Better:

```python
sellable = max(stock.on_hand(sku) - stock.reserved(sku) - safety_margin, 0)
```

- **Why:** a reader must replay the function to know which meaning a later line sees.
- **Fine when:** each step refines the same meaning, such as normalising a string.
- **Spot it:** three or more assignments to one name in a function.

## 7.5 Data kept in step by index

Two lists whose items belong together only because they stay in the same order.

Bad:

```python
skus: list[str] = []
quantities: list[int] = []
for line in order.lines:
    skus.append(line.sku)
    quantities.append(line.quantity)
for sku, quantity in zip(skus, quantities):
    reserve(sku, quantity)
```

Better:

```python
for line in order.lines:
    reserve(line.sku, line.quantity)
```

- **Why:** the alignment is an invariant only the author knows, and an `append` to one list breaks it silently.
- **Fine when:** the lists come from an API that returns columns, and you zip them once at the boundary.
- **Spot it:** two lists appended in the same loop and zipped later.
