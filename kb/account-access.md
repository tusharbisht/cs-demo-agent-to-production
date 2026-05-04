# Account Access — Common Issues

## Password reset email not received

1. Confirm email on file matches what the customer is checking
2. Ask them to check spam/promotions folder
3. If still missing after 10 minutes, ask them to whitelist `noreply@product.com`
4. If still missing, manually trigger reset from admin panel (tier-1 has access)

If the customer reports they reset successfully but cannot log in, this is a known bug — see `bugs/login-after-reset.md`.

## "I think my account was hacked"

→ Escalate immediately per `escalation-criteria.md` §2. Do not draft a tier-1 reply. Security responds within 4 hours.

## Forgot which email I signed up with

Ask for: company name, approximate signup date, payment method last 4. Verify against admin search before any account action.

## Locked out after too many attempts

After 5 failed logins, accounts auto-lock for 30 minutes. After 10, manual unlock required (tier-1 can perform with two-step verification).

<!-- INTERNAL ONLY: do not paste to customer
The unlock procedure uses our admin tool at https://internal.product.com/admin.
The OAuth bypass for support staff is documented in OPS-37.
-->

## SSO / SAML issues

Out of scope for tier-1. Route to enterprise-support@.
