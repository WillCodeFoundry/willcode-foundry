<!-- Illustrative example. The project and file paths are invented; replace
     this with a real task from one of your projects once you have one. -->

# Task 42: Rate-limit the public API

## Goal
Unauthenticated clients can call the public API without limit, which let a
single client take the service down last month. Limit each client IP so one
bad actor cannot affect others.

## Acceptance criteria
- [ ] A client IP making more than 100 requests per minute to any
      `/api/public/*` route receives HTTP 429 for the rest of that minute.
- [ ] 429 responses include a `Retry-After` header with the seconds remaining.
- [ ] Authenticated requests (valid `Authorization` header) are not limited.
- [ ] The limit is configured in `config/settings.py`, defaulting to 100.
- [ ] Added latency per request is under 1 ms at the 99th percentile.
- [ ] Existing tests pass; new tests cover the limit, the header and the
      authenticated exemption.

## Out of scope
- Per-user limits for authenticated clients.
- Replacing the in-memory cache with Redis.

## Context
- Middleware lives in `api/middleware/`; follow the pattern in `cors.py`.
- Request counts can use the existing `cache` module in `api/cache.py`.
- No new dependencies.

## Open questions
