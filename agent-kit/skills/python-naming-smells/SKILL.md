---
name: python-naming-smells
description: How to spot a bad name in Python code and prose. Covers names that fail on sight, names that mislead at their uses, and names that break the words the project already agrees on, each with an invented bad and better name and how to spot it. Use when checking the names a diff adds or renames, before committing, when reviewing, or when naming something.
---

# Python naming smells

A name is good when a reader at one of its uses, with the names around it, can predict what it holds or does. This skill lists the ways names fail that test, and how to spot each. The project's own `AGENTS.md` wins where it says otherwise.

## What to check

Check every name a diff adds or renames, of every kind below. Check too each existing name whose behaviour the diff changes: a `get_` lookup the diff makes write has just become a smell.

| Kind | Examples |
|---|---|
| identifier | module, class, function, method, property, variable, parameter, attribute, exception, file |
| term | an entry added to `GLOSSARY.md` |
| interface name | command, flag, config key, environment variable, branch, and a public function's parameters, which callers pass by keyword |
| prose word | a concept named in a doc, docstring, message, comment or instruction |
| test name | a test function, read as a sentence about the behaviour it shows |

Leave case style and builtin shadowing to ruff's `N` and `A` rules. Neither flags two names that differ only in case.

## How to check

1. **On sight.** Scan each name against "Smells you can see in the name". These need no context.
2. **At its uses.** Read the name at every use in the repository, not only the diff's: `git grep -n -w <name>`. Ask the questions in "Smells at the uses".
3. **Against the project's words.** Search with `git grep -n -w` for the name, and for the other words a reader might use for the concept. Check "Smells against the project's words".
4. **In prose.** In the lines the diff adds to docs, docstrings and messages, check only what "Smells in prose" lists.

## Smells you can see in the name

| Smell | Bad | Better | Why it fails |
|---|---|---|---|
| History in the name | `parse_order_v2`, `new_total`, `legacy_client` | `parse_order`, `total_with_tax`, `courier_client` | It says when the thing was written, not what it is. |
| Numbered siblings | `order1`, `order2` | `original`, `amended` | Only the definition says which is which. |
| A quantity without its unit | `timeout = 30`, `max_size` | `timeout_seconds = 30`, `max_size_bytes` | Only the definition says seconds or milliseconds. |
| A negative boolean | `not_shipped`, `disable_retry=False` | `shipped`, `retry=True` | Its negation reads backwards: `if not not_shipped`. |
| The type or the step in the name | `order_dict`, `parsed_json`, `response_data` | `order`, `order_by_id` | It names how the value was made, not what it is. |
| A word that says nothing | `data`, `info`, `misc`, `result`, `obj`, `item`, `manager`, `helper`, `util`, `handler` | `invoice`, `courier_client` | It fits anything, so it tells the reader nothing. A thing with no honest name usually does two jobs. |
| The module repeated | `order.OrderStatus` | `order.Status` | Callers already read the module's name. |
| A dict named like a list | `prices` for a dict of SKU to price | `price_by_sku` | The name hides the key. |
| A boolean that doesn't ask | `shipping` for a bool, `check_stock` for a bool | `is_shipped`, `has_stock` | It reads as a value or an action, not a yes or no. |
| Grammar that doesn't match the kind | `def invoice(order)` that sends it, `is_status = "paid"` | `send_invoice(order)`, `status = "paid"` | A function is a verb, a value a noun, and only booleans start with is, has, can or should. |
| Names that differ only in case | a function `_draft()` that returns a `_Draft` | `_draft_order()` returning a `_Draft` | Read aloud, the two are one word, so readers mix up the call and the class. An instance `draft = _Draft()` is fine. |
| A possessive in the name | `test_uses_the_shops_own_prices`, `books_isbn` for one book's ISBN | `test_uses_prices_set_by_the_shop`, `isbn` | A name can't hold an apostrophe, so the possessive reads as a plural, or looks misspelt. |
| The vendor in the name | `stripe_refund(order)` called from checkout, `mailchimp_list` | `refund(order)`, `mailing_list` | Callers then name the vendor too, so changing vendor renames them all. Fine inside the vendor's own adapter. |
| An exception named for the fix | `RetryLaterError` | `CourierUnavailable` | An exception names what happened, in the glossary's words when it has one. |

## Smells at the uses

Each asks a question about one use, read as a sentence with the names beside it.

### Needs the definition

The use makes sense only once you have read what the name points to.

```python
process(data, True)  # bad: process what, and what does True switch?
ship(order, express=True)  # better
```

- **Spot it:** read a call site with the definition hidden, and say what it does.

### The wrong kind of thing

A condition that isn't a boolean, a collection that isn't one, or a value that is really an action.

```python
# bad
if order.shipping:
    ...  # a Shipment or None, read as a yes/no
orders = find_order(order_id)  # one order, named as many
total = cart.total  # a property that charges the card

# better
if order.shipment is not None:
    ...
order = find_order(order_id)
receipt = cart.charge()
```

- **Spot it:** a plural holding one value; a noun used in `if`; a property whose body has side effects.

### Reads the opposite of the code

The name reads true where the code makes it false, or the reverse.

```python
def is_expired(token: Token) -> bool:
    return token.expires_at > now()  # bad: true while the token is still valid


def is_expired(token: Token) -> bool:
    return token.expires_at <= now()  # better: the body now does what the name says


def is_valid(token: Token) -> bool:
    return token.expires_at > now()  # better: or the name now says what the body does
```

- **Spot it:** read the body against what the name claims, especially booleans and `can_`/`should_` functions.

### Promises less than it does

A name that reads as a lookup must not write, switch state, call the network, or fail where absence is normal. Its verb promises cost, side effects and failure.

```python
def get_order(order_id: str) -> Order:  # bad: creates and saves when missing
    return orders.get(order_id) or orders.save(Order(order_id))


def load_or_create_order(order_id: str) -> Order: ...  # better
```

- **Spot it:** a `get_`, `find_`, `is_` or `has_` function, or a `@property`, whose body writes, calls out, or raises when the value is missing.

### Too close to another name

The name shares its word with something else in scope, or sits one letter from a name that means something else.

```python
rate = order.tax_rate
rates = fx.rates_for(order.currency)  # bad: rate and rates mean different things

tax_rate = order.tax_rate
exchange_rates = fx.rates_for(order.currency)  # better
```

- **Spot it:** list the names in a scope and look for near pairs: plurals, one-letter differences, `ship` and `shop`.

### Too general for its reach

The name fits while it is the only one, but where it is read holds others: an environment variable, a settings field, an API model, an exported name.

```python
# bad: the delivery integrations read this variable too
COURIER_API_KEY = env["COURIER_API_KEY"]
# better: says which feature owns it
RETURNS_COURIER_API_KEY = env["RETURNS_COURIER_API_KEY"]


class Request(BaseModel): ...  # bad: one of several Request models in one API schema


class RefundRequest(BaseModel): ...  # better
```

- **Spot it:** for each name that leaves its module, ask what else shares its namespace: the process environment, the settings, the schema, everything that imports the package. Search there for the same name.

### Names a neighbour

The name is right for something next to the value: its id instead of its name, a pattern instead of a key, the result of a rule instead of the fact it checks.

```python
# bad
allowed_isbns = [book.title for book in shelf]  # titles, named as ISBNs
needs_review = book.price > 500  # the fact is "expensive"; review is one rule that uses it

# better
allowed_titles = [book.title for book in shelf]
is_expensive = book.price > 500
```

- **Spot it:** read what the name points at, then what the value is built from. A noun from the same domain that isn't this value, such as id and name, file and cache, key and pattern, is a neighbour.

### An underscore that lies

A leading underscore says nothing outside the module or class uses the name.

```python
# bad
from shop.pricing import _round_price  # used outside, so not private


def parse_sku(raw: str) -> str: ...  # in pricing.py, the only module that calls it


# better
from shop.pricing import round_price


def _parse_sku(raw: str) -> str: ...
```

- **Spot it:** `git grep -n -w _name` finds uses in other modules; a public name's only uses are in its own module. A test that imports the name is a use from outside: test through the public name, or drop the underscore.

## Smells against the project's words

The project's agreed word for a concept is, in order: the glossary's (`GLOSSARY.md`, or those a `GLOSSARY-MAP.md` points to), then `DESIGN.md`'s, then a class's own name for its instances, then a word the code uses for that concept and nothing else. A thing that comes from outside, such as a protocol's field, a vendor's parameter or a spec's header, takes the outside system's own term first.

| Smell | Bad | Better | Spot it |
|---|---|---|---|
| A synonym | `basket` where the glossary says `cart` | `cart` | search for the other words a reader might use |
| An avoided word | a word `GLOSSARY.md` lists under _Avoid_ for the concept | the glossary's term | search the glossary's _Avoid_ lists |
| A homonym | `session` for a checkout, where `session` already means a login; `Supplier.shop` for the supplier's shop beside `shop_dir` for ours | `checkout`; `Supplier.storefront` | search for the name; check each hit means the same thing, attributes and parts of longer names included. A rename that needs two new names shows the old one meant two things. |
| An instance named otherwise | `repo = OrderRepository()` | `order_repository = OrderRepository()` | an instance named neither for its class nor for its role |

An instance may be named for its role instead of its class only when the scope holds two of the type, such as `recorded` and `wanted`, or when its role is what the reader needs, such as `destination`.

## Smells in prose

In prose, check only these two:

1. **A word that breaks the agreed one:** a glossary _Avoid_ word, or a synonym for a term the glossary or `DESIGN.md` gives. Judge each hit by its sense; an ordinary word that matches a code identifier isn't one.
2. **A new term that wasn't checked:** a word the prose introduces as a concept's name, marked by backticks, bold, a heading, or a sentence that defines it. Check it like any new name.

Style and clarity in prose are not naming smells.
