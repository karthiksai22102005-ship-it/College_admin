import os
import time
import uuid
from werkzeug.utils import secure_filename
from utils.storage_backend import save_filestorage, delete_upload_rel_path, using_s3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_ROOT = os.path.join(BASE_DIR, "uploads")

# Default allowed extensions and size.
# Some document types (e.g. books/papers) must be restricted further.
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

def init_upload_dirs():
    """Ensures all necessary upload directories exist."""
    if using_s3():
        return
    subdirs = ["photos", "docs/personal", "docs/rd", "docs/qualifications"]
    for d in subdirs:
        os.makedirs(os.path.join(UPLOAD_ROOT, d), exist_ok=True)

def _get_ext(filename: str) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower().strip()


def allowed_file(filename, allowed_exts=None):
    """Checks if the file extension is allowed."""
    ext = _get_ext(filename)
    if not ext:
        return False
    if allowed_exts is None:
        allowed_exts = ALLOWED_EXTENSIONS
    return ext in set(allowed_exts)


def _allowed_exts_for(category: str, tag: str):
    """
    Central place to enforce per-document-type file restrictions.

    - photos: images only
    - personal/qualifications: pdf + images (common scanned docs)
    - rd:
      - book_* / paper_*: documents only (pdf/doc/docx) - NO images
      - everything else (e.g. certifications): pdf + images
    """
    cat = (category or "").strip().lower()
    t = (tag or "").strip().lower()

    if cat == "photos":
        return {"png", "jpg", "jpeg", "gif"}

    if cat in {"personal", "qualifications"}:
        return {"pdf", "png", "jpg", "jpeg"}

    if cat == "rd":
        if t.startswith("book_") or t.startswith("paper_"):
            return {"pdf", "doc", "docx"}
        if t.startswith("material_"):
            return {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "csv", "txt"}
        return {"pdf", "png", "jpg", "jpeg"}

    return ALLOWED_EXTENSIONS

def save_file(file_obj, category, faculty_id, tag="doc"):
    """
    Saves a file securely, with size and type validation.
    - category: 'photos', 'personal', 'rd', 'qualifications'
    - faculty_id: e.g., 'FAC1001'
    - tag: e.g., 'aadhaar', 'pan', 'cert_title'
    """
    if not file_obj or not file_obj.filename:
        raise ValueError("No file provided.")

    allowed_exts = _allowed_exts_for(category, tag)
    if not allowed_file(file_obj.filename, allowed_exts=allowed_exts):
        allowed_str = ", ".join(sorted(allowed_exts))
        raise ValueError(f"File type not allowed for this document. Allowed: {allowed_str}")

    # Check file size
    file_obj.seek(0, os.SEEK_END)
    file_length = file_obj.tell()
    if file_length > MAX_FILE_SIZE:
        raise ValueError(f"File is too large. Max size is {MAX_FILE_SIZE // 1024 // 1024} MB.")
    file_obj.seek(0) # Reset file pointer

    if category == "photos":
        subfolder = "photos"
    elif category in ("personal", "rd", "qualifications"):
        subfolder = os.path.join("docs", category)
    else:
        subfolder = "docs"

    # Sanitize tag for filename
    safe_tag = secure_filename(tag)[:50] # Limit tag length

    # Generate secure filename: FAC1001__aadhaar__17098822.pdf
    ext = file_obj.filename.rsplit('.', 1)[1].lower()
    timestamp = int(time.time())
    unique = uuid.uuid4().hex[:10]
    new_filename = f"{faculty_id}__{safe_tag}__{timestamp}__{unique}.{ext}"
    
    key = f"uploads/{subfolder.replace(os.sep, '/')}/{new_filename}"
    save_filestorage(file_obj, key)

    # Return relative path for DB storage, using forward slashes
    rel_path = f"/{key}"
    return rel_path

def delete_file(rel_path):
    """
    Deletes a file given its relative path from the 'uploads' directory.
    - rel_path: e.g., '/uploads/docs/personal/file.pdf'
    """
    if not rel_path or not rel_path.startswith('/uploads/'):
        print(f"Warning: Attempted to delete invalid path: {rel_path}")
        return False

    return delete_upload_rel_path(rel_path)
