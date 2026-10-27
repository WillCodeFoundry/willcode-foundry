# Test sandbox code in-process against a modelled machine; real sandboxes only for what nothing else shows

Hardening needs root and a real sandbox, which most test runs don't have. So it acts on a `Machine` describing what it touches, and the tests run root mode, then agent mode, on one temporary machine, in-process. Tests in real containers (`-m docker`) and real sbx sandboxes (`-m sbx`) check only what the model can't: real permissions, the read-only mount, sbx itself.

## Considered options

- **Testing each step and check on its own.** Every part passed alone, while the sequence crashed on every relaunch.

Source: #20.
