# Cloud Deployment Prep

This app now supports a storage backend switch for both:
- `data/*.store` records
- `uploads/*` documents

## 1) Required Environment Variables

Set these in your deployment platform:

```env
STORAGE_BACKEND=s3
S3_BUCKET=your-bucket-name
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
S3_KEY_PREFIX=college-admin-prod
# Optional for S3-compatible providers (Cloudflare R2, MinIO, etc.)
S3_ENDPOINT_URL=
```

Optional:

```env
ALLOW_LEGACY_ADMIN_LOGIN=false
```

## 2) Local to Cloud Migration (One-time)

When `STORAGE_BACKEND=s3` is enabled, new writes go to cloud.
To migrate existing local data:

1. Upload everything under `data/` and `uploads/` to your S3 bucket.
2. Preserve relative keys:
   - `data/faculty.store`
   - `data/users.store`
   - `data/audit_logs.store`
   - `uploads/docs/...`
3. Keep app paths unchanged; backend resolves same keys.

## 3) Audit Logs Excel

Admin can download logs at:

- `GET /admin/export/audit-logs?limit=5000`

This generates an Excel file with timestamp, actor, action, target, and metadata.

## 4) Forgot Password Flow

`POST /auth/forgot-password`

Payload:

```json
{
  "username": "FAC1001",
  "role": "faculty",
  "dob": "18-03-1984",
  "new_password": "Strong@123"
}
```

For admin reset:

```json
{
  "username": "ADMIN001",
  "role": "admin",
  "new_password": "Strong@123"
}
```

Password policy:
- min 8 chars
- uppercase + lowercase + digit + special char
