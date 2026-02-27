# College ERP RBAC Implementation (Current Codebase)

## Implemented Foundations

- Designation-to-role normalization:
  - `HOD` -> `HOD`
  - contains `ASSOC` -> `ASSOC_PROF`
  - contains `ASST` -> `ASST_PROF`
  - else -> `STAFF`
- Stored fields:
  - `designation` (original)
  - `normalized_role` (derived)
  - `role` (system role mirror)
  - `permissions_json` (role-based defaults with admin override)
- Account security:
  - `account_locked` enforced during login
  - Login lockout by attempts/IP already present
  - Passwords hashed via Werkzeug security
- Admin controls:
  - faculty create/update with role normalization
  - lock/unlock endpoint
  - reset password endpoint
  - impersonate faculty dashboard endpoint
- Faculty dashboard:
  - Role badge
  - Role workspace actions rendered by normalized role

## New / Updated Admin APIs

- `POST /admin/impersonate/<faculty_id>`
- `POST /admin/impersonation/stop`
- `PUT /admin/faculty/<faculty_id>/lock` body: `{ "locked": true|false }`
- `POST /admin/faculty/<faculty_id>/reset-password` body: `{ "new_password": "..." }`

## Migration Utility

- Run `python migrate_roles_permissions.py` once to backfill normalized role and permissions.

## Notes

- Existing app currently uses DB-backed key/value store with structured JSON payloads.
- Core RBAC and authorization checks are backend enforced.
