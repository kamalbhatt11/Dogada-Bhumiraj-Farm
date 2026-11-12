# Asset and dependency license audit (29 October 2026)

This is an inventory, not a legal certification. Source provenance for the images bundled in the uploaded ZIP was not provided, so ownership/license cannot be verified from the files alone. Before public use, confirm that the farm owns or has permission to use each image and logo; remove any image without a documented right to use it. In particular review all files under `app/static/images/`, including `watermark of krbcreaton.png`, payment QR images, product photos and farm photos.

## Fonts
- Removed remote Google Fonts requests from the base template. The CSS now falls back to locally available/system fonts, avoiding third-party font requests.

## Python dependencies declared in `requirements.txt`
- Flask 3.1.2 — BSD-3-Clause
- Flask-SQLAlchemy 3.1.1 — BSD-3-Clause
- Flask-Login 0.6.3 — MIT
- Werkzeug 3.1.3 — BSD-3-Clause
- Flask-WTF 1.2.2 — BSD-3-Clause
- requests — Apache-2.0
- psycopg[binary] — LGPL-3.0-or-later (psycopg 3 licensing includes LGPL/commercial alternatives; verify the exact installed distribution and dependencies)
- gunicorn — MIT

Versions may pull transitive dependencies. Generate a complete SBOM and check each resolved package's license with your actual deployment lockfile before release. No lockfile was included in the uploaded archive, so a complete dependency/license audit is not possible from requirements alone.

## Third-party runtime services
- OpenStreetMap tile service and public OSRM demo routing are contacted by the checkout map/routing feature. These are not advertising trackers, but they are external services and may receive technical request data and delivery coordinates. The OSRM public demo is not a production SLA.
- No analytics/advertising tracker, marketing email system, recurring billing system, or AI-training integration was found in the reviewed source templates/routes. Re-audit after adding any integration.

## Logos and marketing email
- The site currently displays farm branding and a `watermark of krbcreaton.png` asset; confirm permission/ownership before deployment. No customer logo placements or marketing-email sender were found in the reviewed project. If marketing email is added, include a working unsubscribe mechanism in every marketing message.
