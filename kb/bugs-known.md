# Known Bugs — Tier-1 Reference

## login-after-reset (BUG-2401)

**Symptom:** After a password reset, customer cannot log in with the new password. Receives "invalid credentials."

**Root cause:** Session token cache invalidation race in auth-service. Reset succeeds in DB but cached old session blocks login for up to 30 minutes.

**Tier-1 response:** Apologise. Ask customer to wait 30 minutes and try again. If still failing, escalate (token cache may need manual flush).

**Status:** Fix in progress, ETA 2026-Q2.

## dashboard-slow-large-datasets (BUG-1972)

**Symptom:** Dashboard takes 30+ seconds to load for accounts with > 100k rows of source data.

**Root cause:** Inefficient query plan when filters include date ranges > 90 days.

**Tier-1 response:** Suggest narrowing the date filter or breaking dashboard into smaller views. **Do not promise a fix timeline.** Engineering tracks at BUG-1972; status updates in #dashboard-perf.

**Workaround:** None at the dashboard level. Custom queries via API are not affected.

## csv-export-truncation (BUG-2155)

**Symptom:** CSV export truncates at 10,000 rows.

**Root cause:** Hard limit, intentional for performance. Documented as a feature but customers expect it to be a bug.

**Tier-1 response:** Explain it's a documented limit. Offer the API export endpoint (no row cap). Link to API docs.

## Stale entries to remove

> **TODO (eng-ops, 2026-01-04):** the entries below are for bugs fixed > 6 months ago. Schedule a KB cleanup. For now, tier-1 should disregard them.

- ~~`safari-login-fails`~~ — fixed 2025-08
- ~~`mobile-app-crash-on-launch`~~ — fixed 2025-09
- ~~`webhook-duplicate-delivery`~~ — fixed 2025-10
