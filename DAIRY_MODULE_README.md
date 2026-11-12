# Shree Dogada Farm — Dairy Management Module

This module extends the existing Flask/SQLAlchemy application. It does not replace the public shop, owner login, livestock, or vaccination sections.

## Included
- Owner-only dairy dashboard and customer account creation (owner assigns username/password).
- Customer portal with own delivery history, ledger, payments, balance, and correction requests.
- Per-customer regular product quantities with effective dates and historical quantity records.
- Daily delivery register prefilled from active regular quantities; delivered/no-delivery states, decimal L/kg quantities, late entry by selecting an earlier date, and owner corrections.
- One-time extra orders with price snapshots.
- Customer ledger, cash/eSewa/Khalti/bank payment recording, optional selected-charge allocation, and unallocated credit.
- Customer statements with print / browser Save as PDF, and CSV ledger export.
- Temporary/indefinite pause status, resume, and customer request review.
- Add dairy products dynamically using L or kg units.
- Audit records for key owner actions.

## URLs
- Owner dairy dashboard: `/dairy/owner` (requires existing owner login)
- Daily delivery register: `/dairy/owner/deliveries`
- Extra orders: `/dairy/owner/extra`
- Payments: `/dairy/owner/payments`
- Customer requests: `/dairy/owner/requests`
- Customer login: `/dairy/customer/login`

## Database behaviour
New tables are created by the existing `db.create_all()` startup call. Existing tables and `instance/farm.db` are not dropped or replaced. The delivery table has a uniqueness constraint on customer + product + date. Charges are ledger entries, and statements group ledger charges rather than creating duplicate charges. Prices and quantities are stored as database Numeric values for new dairy records.

## Deployment / first run
1. Back up your existing database before deploying any update.
2. Deploy the complete project folder using the existing Render service and existing environment variables.
3. Keep the existing `SECRET_KEY`, database URL, and owner credentials unchanged.
4. Sign in through the existing `/owner/login`, then open `/dairy/owner`.
5. Create customer accounts and provide their credentials privately.

No paid service, payment gateway integration, or new API key is required. Payment methods are recorded manually; this does not automatically verify eSewa/Khalti/bank transactions.

## Important current-scope notes
This is an initial integrated implementation, not a substitute for a production accounting audit. Statement periods are entered by the owner; automatic scheduled invoice generation, complete PDF file generation (browser print is available), invoice-specific allocation UI/reallocation, payment reversal workflow, customer password reset UI, archive/delete workflow, automatic backups, and fully automated online-order-to-customer matching are not yet implemented. Existing public online orders continue to use the existing order system and are not silently copied into dairy balances. Staff share the owner login, so they have owner-level permissions. Render free-instance disk persistence and backup availability depend on the service configuration; do not assume SQLite files on an ephemeral disk are permanent.

## Verification
Python source files were syntax-compiled during packaging. A full Flask runtime test could not be executed in the packaging environment because Flask dependencies were not installed and network access was unavailable. Run the project's requirements installation and smoke tests in the deployment environment before using it with live customer accounts or balances.
