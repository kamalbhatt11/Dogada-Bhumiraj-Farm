# Livestock extension

This package is based on the uploaded project. The original ZIP remains your backup.

## Start

1. Keep a separate backup of `instance/farm.db` before launching this version.
2. Install dependencies: `pip install -r requirements.txt`.
3. If installing without an existing admin, set `INITIAL_OWNER_PASSWORD` to a strong password of at least 10 characters before first run. Existing admin passwords remain unchanged.
4. Set a strong `SECRET_KEY` environment variable.
5. Run `python run.py`. Visit `/owner/login`, `/owner/animals`, and `/livestock`.

`db.create_all()` creates the new `animal` and `vaccination` tables in the existing SQLite database; it does not delete existing orders, products or customers. For future schema changes use proper migrations.

Photos are stored in `instance/animal_uploads`. On Render, use a persistent disk or object storage for BOTH the SQLite database and uploaded photos; an ephemeral filesystem loses changes across redeploys. Set `DATABASE_URL` accordingly.

Existing default admin passwords should be changed immediately. Existing routes do not implement CSRF protection; add Flask-WTF/CSRF before public production use, particularly for owner forms.

Vaccination due reminders are based only on dates entered by the owner, not veterinary recommendations.
