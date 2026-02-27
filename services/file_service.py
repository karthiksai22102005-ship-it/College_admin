import os
from werkzeug.utils import secure_filename

UPLOAD_PHOTO_DIR = os.path.join("uploads", "photos")
UPLOAD_DOC_DIR = os.path.join("uploads", "docs")

ALLOWED_DOC_EXT = {"pdf", "jpg", "jpeg", "png"}
ALLOWED_IMG_EXT = {"jpg", "jpeg", "png"}


def ensure_dirs():
    os.makedirs(UPLOAD_PHOTO_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DOC_DIR, exist_ok=True)


def allowed_file(filename, allowed_set):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_set


def save_photo(file, faculty_id):
    ensure_dirs()

    if not allowed_file(file.filename, ALLOWED_IMG_EXT):
        return None

    filename = secure_filename(f"{faculty_id}_photo.{file.filename.rsplit('.',1)[1]}")
    path = os.path.join(UPLOAD_PHOTO_DIR, filename)
    file.save(path)
    return path


def save_document(file, faculty_id, qual_type):
    ensure_dirs()

    if not allowed_file(file.filename, ALLOWED_DOC_EXT):
        return None

    ext = file.filename.rsplit(".", 1)[1]
    filename = secure_filename(f"{faculty_id}_{qual_type}.{ext}")
    path = os.path.join(UPLOAD_DOC_DIR, filename)
    file.save(path)
    return path
