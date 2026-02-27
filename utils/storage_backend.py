import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _backend():
    return str(os.getenv("STORAGE_BACKEND", "local")).strip().lower()


def using_s3():
    return _backend() == "s3"


def _s3_client_and_bucket():
    try:
        import boto3
    except Exception as exc:
        raise RuntimeError("STORAGE_BACKEND=s3 requires boto3 to be installed") from exc

    bucket = os.getenv("S3_BUCKET", "").strip()
    if not bucket:
        raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")

    region = os.getenv("AWS_REGION", "").strip() or None
    endpoint_url = os.getenv("S3_ENDPOINT_URL", "").strip() or None
    aws_key = os.getenv("AWS_ACCESS_KEY_ID", "").strip() or None
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip() or None

    client = boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint_url,
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
    )
    return client, bucket


def _s3_key_prefix():
    raw = str(os.getenv("S3_KEY_PREFIX", "")).strip().strip("/")
    return f"{raw}/" if raw else ""


def _norm_key(key):
    clean = str(key or "").strip().replace("\\", "/").lstrip("/")
    return clean


def path_to_storage_key(path):
    value = str(path or "")
    if not value:
        return ""
    if value.startswith("/uploads/"):
        return value.lstrip("/")
    if os.path.isabs(value):
        rel = os.path.relpath(value, BASE_DIR)
    else:
        rel = value
    return _norm_key(rel)


def write_bytes(key, data_bytes, content_type=None):
    key = _norm_key(key)
    payload = data_bytes if isinstance(data_bytes, (bytes, bytearray)) else bytes(data_bytes)
    if using_s3():
        client, bucket = _s3_client_and_bucket()
        kwargs = {"Bucket": bucket, "Key": f"{_s3_key_prefix()}{key}", "Body": payload}
        if content_type:
            kwargs["ContentType"] = content_type
        client.put_object(**kwargs)
        return

    abs_path = os.path.join(BASE_DIR, key.replace("/", os.sep))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(payload)


def read_bytes(key):
    key = _norm_key(key)
    if using_s3():
        client, bucket = _s3_client_and_bucket()
        try:
            obj = client.get_object(Bucket=bucket, Key=f"{_s3_key_prefix()}{key}")
        except Exception:
            return None
        return obj["Body"].read()

    abs_path = os.path.join(BASE_DIR, key.replace("/", os.sep))
    if not os.path.exists(abs_path):
        return None
    with open(abs_path, "rb") as f:
        return f.read()


def delete_key(key):
    key = _norm_key(key)
    if not key:
        return False
    if using_s3():
        client, bucket = _s3_client_and_bucket()
        client.delete_object(Bucket=bucket, Key=f"{_s3_key_prefix()}{key}")
        return True

    abs_path = os.path.join(BASE_DIR, key.replace("/", os.sep))
    if os.path.exists(abs_path):
        try:
            os.remove(abs_path)
            return True
        except OSError:
            return False
    return False


def save_filestorage(file_obj, key):
    key = _norm_key(key)
    if using_s3():
        data = file_obj.read()
        file_obj.stream.seek(0)
        write_bytes(key, data, content_type=getattr(file_obj, "mimetype", None))
        return

    abs_path = os.path.join(BASE_DIR, key.replace("/", os.sep))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    file_obj.save(abs_path)


def read_upload_rel_path(rel_path):
    if not rel_path:
        return None
    key = _norm_key(str(rel_path).lstrip("/"))
    return read_bytes(key)


def delete_upload_rel_path(rel_path):
    if not rel_path:
        return False
    key = _norm_key(str(rel_path).lstrip("/"))
    return delete_key(key)
