# Names

| Name | Kind | Where | Why |
|---|---|---|---|
| `sbx-0001` (was `sbx-smoke`) | interface name (task id) | `tests/sbx/test_smoke.py`, `CONTRIBUTING.md` | The pattern refuses `sbx-smoke`; TASK.md lists the sbx test among the fixtures to move. Prefix `sbx` keeps the tier's name. Its sandbox becomes `dev-foundry-test-sbx-0001`. |
| `tst-`, `cls-` ids | test fixture ids | `tests/` | Replace `t0`/`t1`/`T1`… and `c0`: `tst-0000` is the fixture's open task, `cls-0000` its closed one, `tst-00001` keeps the old `t01` prefix-sibling case. |
| `KELVIN` | constant | `tests/test_task.py` | New word for U+212A in the refused-ids test; no existing name found for it (searched: kelvin, 212a). |
