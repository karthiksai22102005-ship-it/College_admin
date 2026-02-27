# Free Deployment + Database Plan

This app no longer depends on `.store` files for active persistence.
It now stores data in a database backend through `utils/data_store.py`:

- `DB_BACKEND=sqlite` (default, local)
- `DB_BACKEND=postgres` (recommended for online deployment)

## 1) Local Database Migration

From project root:

```powershell
python migrate_to_database.py
```

This migrates known datasets (`faculty/users/audit_logs/notifications`) into the configured DB backend.

## 2) Recommended Free Online Stack

- Host app: **Render Web Service** (Free tier is available, with usage limits)
- DB: **Render PostgreSQL Free** (intended for testing/dev, limited features)

Set these env vars in deployment:

- `DB_BACKEND=postgres`
- `DATABASE_URL=<your postgres connection URL>`
- `SECRET_KEY=<strong-random-secret>`
- `SESSION_COOKIE_SECURE=true`
- `SESSION_COOKIE_SAMESITE=Lax`
- `ALLOW_LEGACY_ADMIN_LOGIN=false`

## 3) Build / Start Commands

- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`

(`Procfile` already contains `web: gunicorn app:app`)

## 4) First Deploy Migration

After deploy, run once in shell:

```powershell
python migrate_to_database.py
```

Then verify:

1. Admin login works
2. Faculty list loads
3. Faculty profile update persists after restart

## 5) Notes

- SQLite is okay for local/single-instance usage.
- For concurrent online usage, use PostgreSQL.
- Keep legacy files only as backup after successful migration.

## Official References

- Render pricing (free tier details): https://render.com/pricing
- Render free PostgreSQL limitations: https://render.com/docs/free#free-postgresql-instance-limitations
- Render PostgreSQL docs: https://render.com/docs/postgresql
