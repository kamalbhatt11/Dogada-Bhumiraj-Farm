# Security review notes — Shree Dogada Farm

## Changes applied in this pass

- Production startup now fails closed if `SECRET_KEY` is missing. A local-only development key remains available for local testing.
- Production mode enables Secure session cookies and trusts one Render proxy hop for HTTPS/client IP detection. Flask-Login session protection is set to `strong`.
- CSRF remains globally enabled. Owner logout is now POST-only and includes a CSRF token.
- Added a database-backed 5-failure / 15-minute owner login lockout. Only a keyed SHA-256 digest of the client IP is stored.
- Added baseline Content Security Policy and other browser security headers. HSTS is sent only when the request is HTTPS.
- Private owner, data-rights and order receipt responses are marked `Cache-Control: no-store` and `X-Robots-Tag: noindex, nofollow`.
- Public order receipt references use 104 bits of random entropy while remaining within the existing 30-character database column.
- Added maximum-length validation for public inquiries.
- Removed the unused destructive clear-all-orders endpoint.
- Added responsive CSS overrides without replacing the existing visual theme or cart JavaScript.

## Remaining deployment tasks (required)

1. Set `APP_ENV=production`, a unique random `SECRET_KEY`, `SESSION_COOKIE_SECURE=true`, and a unique `INITIAL_OWNER_PASSWORD` (only if creating the first owner) in the host dashboard. Remove `INITIAL_OWNER_PASSWORD` and any `RESET_OWNER_PASSWORD` after use.
2. Use persistent PostgreSQL and verify database backups/restore. `db.create_all()` creates the new login-attempt table but does not migrate existing columns; this pass deliberately kept the order-code column at its existing length.
3. Confirm HTTPS and the final `SITE_URL`; test the CSP in browser developer tools, especially Leaflet map tiles and the OSRM routing call.
4. The public OSRM demo endpoint is not a production SLA service. Choose a supported routing provider or self-host routing before relying on automated delivery fees.
5. Audit and pin the complete Python and npm dependency trees; run `pip-audit` and `npm audit` in an internet-connected development environment.
6. Run automated tests, browser testing at 320/360/390/430/768/1024/1366/1920 CSS pixels, keyboard/screen-reader/contrast checks, and an independent penetration test before handling real customer data.
7. Review image/logo permissions and the privacy/legal drafts with an appropriate professional.

## Important limitations

No software can be promised secure against every possible threat. This pass does not implement payment-provider verification, WAF/DDoS protection, durable file storage, centralized monitoring/alerting, or a full account/customer authentication system. The current CSP permits inline scripts/styles because the existing templates contain inline code; moving those to external files and using nonces/hashes is a future hardening step.

## Applied security hardening (12 November 2026)

- Added persistent per-IP throttling for dairy-customer login (five failed attempts in a 15-minute window, then a 15-minute lockout). Only an HMAC digest of the client IP is stored.
- Rotated the session on successful dairy-customer login and made that portal session temporary with the configured session lifetime.
- Changed clickjacking protection to `X-Frame-Options: DENY` and CSP `frame-ancestors 'none'` because this application does not require embedding.
- Added a generic 500 error page. Unexpected dairy-operation exceptions are logged server-side and a generic message is shown to the user instead of exposing exception text.
- Expanded `.gitignore` to exclude the complete runtime `instance/` directory, database files and uploads from source-control commits.
- Added the `dairy_login_attempts` table; `db.create_all()` creates it on existing installations without deleting existing data.

## Remaining launch blockers / items requiring operator action

- The app still uses `db.create_all()` rather than Alembic/Flask-Migrate. Use explicit migrations for future schema changes; back up the database before deploying.
- Configure a persistent PostgreSQL database, encrypted backups and a tested restore process. SQLite on ephemeral hosting is not suitable for production records.
- Configure and verify a real payment-provider integration before accepting online eSewa/Khalti payments. The current checkout does not verify online payment webhooks and only offers cash/bank transfer.
- The public OSRM routing service is a third-party dependency with no production SLA. Review its privacy implications and replace or contract for a suitable service before scaling.
- The current data-rights form is order-code/phone based and is not full dairy-customer account deletion. A verified account-level export/deletion workflow remains to be designed with retention rules.
- CSP still permits inline scripts and styles to preserve existing templates. Move inline code to static files and use nonces/hashes before tightening it.
- No automated penetration test, dependency vulnerability scan, full browser workflow test, or accessibility audit was run in this environment. Run these before production launch.
