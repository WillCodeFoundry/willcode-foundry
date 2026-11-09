<!-- Illustrative example. The project and file paths are invented; replace
     this with a real task from one of your projects once you have one. -->

# Task 42: Rate-limit the public API

## Goal
Unauthenticated clients can call the public API without limit, which let a
single client take the service down last month. Limit each client IP so one
bad actor cannot affect others.

## Acceptance criteria
- [ ] AC1: A client IP making more than 100 requests per minute to any
      `/api/public/*` route receives HTTP 429 for the rest of that minute.
- [ ] AC2: 429 responses include a `Retry-After` header with the seconds remaining.
- [ ] AC3: Authenticated requests (valid `Authorization` header) are not limited.
- [ ] AC4: An operator can change the limit in the settings, and it defaults to 100.
- [ ] AC5: Added latency per request is under 1 ms at the 99th percentile.

## Out of scope
- OS1: Per-user limits for authenticated clients.
- OS2: Limits that hold across several servers: each server counts its own requests.

## Risks
- A client behind a shared proxy shares its IP with others, so one heavy user
  limits them all.

## Terms
- **Rate limit**: the most requests a client IP may make to the public API in a minute.

## Open questions
