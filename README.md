# Shree Dogada Farm — Flask Shop

A Flask website for the farm, with product listings, cart, checkout, customer inquiries, owner order management, and livestock/vaccination records.

## Run locally (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
python run.py
```

Open `http://127.0.0.1:5000`.

## Before public deployment

Set these environment variables in the hosting provider:

- `SECRET_KEY`: a long random secret (generate one with `python -c "import secrets; print(secrets.token_hex(32))"`).
- `APP_ENV=production` (or Render's `RENDER=true`) to activate production safeguards.
- `INITIAL_OWNER_PASSWORD`: a strong, unique password of at least 12 characters if the database does not already contain the owner account. This is only used to create the first owner.
- `DATABASE_URL`: recommended PostgreSQL connection URL for persistent production data. Without it, the app uses SQLite at `instance/farm.db`; that may be lost on hosts with ephemeral filesystems.
- `SITE_URL`: the final public website origin, e.g. `https://your-site.example`.
- `SESSION_COOKIE_SECURE=true` when served over HTTPS (enabled automatically in production mode).

The owner username is `owner`. Existing owner accounts retain their existing password. To reset an existing owner password, set `RESET_OWNER_PASSWORD` to a strong password for one deployment/start, then remove that variable after confirming the reset. Do not leave reset variables configured permanently.

## Hosting notes

This is a server-rendered Flask application, not a static-only site. Netlify Drop, GitHub Pages, and Cloudflare Pages cannot run this conventional Flask server directly. Use a Python-capable host (the included `Procfile` starts it with Gunicorn). A separate static frontend on Netlify would require a larger frontend/backend split.

Free hosting plans, databases, and file storage have limits and may sleep or delete temporary files. Back up your database and use persistent PostgreSQL plus durable object storage before relying on this for real customer orders.

## Security and payment notes

- POST forms use CSRF tokens.
- Owner login attempts are throttled using a database table keyed by a keyed IP digest, so the lockout persists across app workers and restarts.
- Production refuses to start without `SECRET_KEY`; production sessions use Secure, HttpOnly and SameSite=Lax cookies.
- CSRF protection is enabled globally; logout is POST-only; private/receipt responses are marked no-store and noindex.
- Security headers include CSP, frame restrictions, MIME sniffing protection, referrer policy, permissions policy and HSTS on HTTPS. Inline scripts/styles remain allowed by the current templates, so CSP can be tightened further after those are moved to external files.
- Order receipt references now use 104 bits of random entropy to make public receipt URLs impractical to guess.
- The unused destructive clear-all-orders endpoint was removed.
- eSewa and Khalti are hidden from checkout until a verified integration is added. Bank QR transfers are manual and are not automatically verified; the farm must confirm receipt.
- Never commit `.env`, database files, uploaded customer data, or credentials to a public repository.
- The free public OSRM routing endpoint is not guaranteed for production traffic.

## Test

```powershell
python -m compileall app config.py run.py index.py
```

Please test a sample checkout, owner login, product update, and livestock upload before using the site for real orders.


## Cart and privacy/legal updates (29 October 2026)

- Cart totals now reflect only items actually saved by pressing **Add to cart**; quantity selection is a draft and no longer changes the subtotal prematurely. Cart rendering uses DOM text nodes for product labels.
- Added draft Privacy Policy, Terms of Service, Subprocessor List, Business DPA template and order-data export/deletion form. These are implementation drafts, not legal advice or a guarantee of legal compliance; have a Nepal-qualified lawyer review them.
- Checkout requires an explicit Terms/Privacy acceptance checkbox, checked server-side.
- Added Accept and Reject optional choices. The current application has no analytics/advertising trackers; cart storage is essential browser storage. Checkout still contacts OpenStreetMap and a public OSRM routing service, which are disclosed on checkout and in the privacy notice.
- Removed remote Google Fonts loading. System-font fallbacks are used.
- Added focus-visible styling and reduced-motion support, but a complete WCAG audit with keyboard, screen-reader, contrast and automated testing is still required.
- `ASSET_LICENSE_AUDIT.md` records unresolved image provenance and dependency-license caveats. Confirm image/logo permissions and audit the full resolved dependency tree before public deployment.
- The application has no subscriptions/recurring billing, no configured AI-training feature and no marketing email sender in the reviewed source. If these are added later, re-review terms, consent, unsubscribe and data-use controls.

## Data rights endpoint

Customers can open `/data-rights`, then enter an order code and phone number to download that order's data as JSON or erase direct identifiers from the active order record. This is not a full account-level data management system; the site currently has no customer accounts. Verify requests carefully and follow applicable retention obligations.


## Responsive and security update (November 2026)

- Added `app/static/css/responsive.css` as an additive responsive layer; existing `style.css`, colour palette, imagery, content, cart JavaScript and business workflows are retained.
- Added responsive overrides for home sections, product grids, checkout/payment, order filters, owner dashboard tabs, forms, cards and footer at common phone/tablet breakpoints.
- Added a database-backed owner-login lockout table (`login_attempt`) using a keyed digest rather than storing raw IP addresses. The table is created automatically on startup.
- Existing database data is not included in the source ZIP. Keep your local `instance/farm.db` and uploaded `instance/animal_uploads` directory when replacing source files.
- This is a code-level hardening pass, not a guarantee against every attack or a substitute for a professional penetration test. Before live orders, configure a persistent PostgreSQL database, strong production secret, backups, domain HTTPS, hosting protections, and review all third-party services and asset licences.

## Additional security checks (12 November 2026)

- Dairy customer login now has database-backed throttling (5 failed attempts / 15 minutes, followed by a 15-minute lockout), with HMAC-digested IP identifiers rather than raw IP storage.
- Dairy-customer sessions are rotated on successful login and are marked temporary.
- Frame embedding is denied using `X-Frame-Options: DENY` and CSP `frame-ancestors 'none'`.
- Unexpected dairy operation errors are logged server-side and shown as generic messages; a generic HTTP 500 page is available.
- The source ZIP excludes the runtime database. Keep a separate encrypted backup of your production database and never upload it to a public repository.
- `db.create_all()` creates new tables but does not migrate changed columns. Add Flask-Migrate/Alembic before making future schema changes.

See `SECURITY_REVIEW.md` for what remains unverified and the launch checklist. This is a code-level hardening pass, not a penetration-test certification.
