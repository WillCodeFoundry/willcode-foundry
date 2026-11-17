# Plan: <task id>

<!-- The dev's: how it will build what TASK.md asks, approved before any code. It holds decisions, not code, and its length follows them: a one-line fix needs a three-line plan. Leave out a section the task has nothing for. -->

## Approach
<How the change works, in a few sentences, and the alternative you turned down, with the criterion, out-of-scope line, rule or ADR it breaks. Leave a judgement call open, with what each option costs.>

## Shape
<The calls the change adds or changes, as a plain-text tree from the entry point, each marked new, changed or unchanged:>

```
<entry point>
└─ <call>   <new, changed or unchanged>
```

## Steps
1. <A refactor the change needs comes first, in commits that change no behaviour. Then the behaviour change.>

## Names
| Change | Name | Signature | Its word comes from |
|---|---|---|---|
| <added, changed, renamed or removed> | <each public name> | <its parameters and return type> | <the glossary, the code, or why a new word> |

## Errors
- <Each message a user or caller can see, word for word.>

## Tests
- AC1: <The test that will show it, at which seam, and the test helpers it uses. An AC no test can show says why.>
- <A test no AC needs, with the bug it catches.>

## Docs
- <Each doc and docstring, modules' and classes' included, the change makes untrue. A docstring listing what its module holds is cut, not extended, as `python-smells` 8.4 says.>
