from flask import Blueprint, request, jsonify, current_app
from utils.data_store import load_data, save_data
from utils.guards import role_required
from utils.file_handler import save_file, delete_file
from utils.audit_service import log_event
from utils.notification_service import push_notification
import os
import uuid

research_bp = Blueprint("research_bp", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACULTY_STORE = os.path.join(BASE_DIR, "data", "faculty.store")


def find_faculty(faculty_list, faculty_id):
    for i, fac in enumerate(faculty_list):
        if fac.get("faculty_id") == faculty_id:
            return i, fac
    return None, None

def find_cert(faculty, cert_id):
    for i, cert in enumerate(faculty.get("certifications", [])):
        if cert.get("cert_id") == cert_id:
            return i, cert
    return None, None


def find_item(items, key, value):
    for i, item in enumerate(items):
        if item.get(key) == value:
            return i, item
    return None, None


@research_bp.route("/faculty/<faculty_id>", methods=["GET"])
@role_required("admin")
def get_research_assets(faculty_id):
    """Gets all research assets for a single faculty."""
    faculty_list = load_data(FACULTY_STORE)
    _, faculty = find_faculty(faculty_list, faculty_id)
    
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404
        
    return jsonify({
        "certifications": faculty.get("certifications", []),
        "books": faculty.get("books", []),
        "research_papers": faculty.get("research_papers", [])
    })

# ======================================================
# CERTIFICATIONS - ADMIN
# ======================================================

@research_bp.route("/faculty/<faculty_id>/certifications", methods=["POST"])
@role_required("admin")
def add_certification(faculty_id):
    """Adds a new certification for a faculty member."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files["file"]
        title = request.form.get("title")
        issuer = request.form.get("issuer")
        year = request.form.get("year")

        if not all([title, issuer, year, file]):
            return jsonify({"error": "Missing required fields: title, issuer, year, file"}), 400

        rel_path = save_file(file, category="rd", faculty_id=faculty_id, tag=title)

        new_cert = {
            "cert_id": "cert-" + str(uuid.uuid4()),
            "title": title,
            "issuer": issuer,
            "year": year,
            "file": rel_path,
            "verified": False # Admin-added certs are unverified by default, can be verified in a separate step
        }

        faculty_list = load_data(FACULTY_STORE)
        idx, faculty = find_faculty(faculty_list, faculty_id)

        if not faculty:
            return jsonify({"error": "Faculty not found"}), 404

        faculty.setdefault("certifications", []).append(new_cert)
        faculty_list[idx] = faculty
        save_data(FACULTY_STORE, faculty_list)
        log_event("admin", "admin", "add_certification", "faculty", faculty_id, {"cert_id": new_cert.get("cert_id")})
        push_notification("faculty", faculty.get("username"), "Certification Added", f"Certification '{title}' added by admin.")

        return jsonify({"message": "Certification added", "certification": new_cert}), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error adding certification: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

@research_bp.route("/faculty/<faculty_id>/certifications/<cert_id>", methods=["PUT"])
@role_required("admin")
def update_certification(faculty_id, cert_id):
    """Updates a certification's metadata."""
    data = request.json
    title = data.get("title")
    issuer = data.get("issuer")
    year = data.get("year")

    if not all([title, issuer, year]):
        return jsonify({"error": "Missing required fields: title, issuer, year"}), 400

    faculty_list = load_data(FACULTY_STORE)
    fac_idx, faculty = find_faculty(faculty_list, faculty_id)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    cert_idx, cert = find_cert(faculty, cert_id)
    if not cert:
        return jsonify({"error": "Certification not found"}), 404
        
    cert["title"] = title
    cert["issuer"] = issuer
    cert["year"] = year
    
    faculty["certifications"][cert_idx] = cert
    faculty_list[fac_idx] = faculty
    save_data(FACULTY_STORE, faculty_list)
    log_event("admin", "admin", "update_certification", "faculty", faculty_id, {"cert_id": cert_id})
    push_notification("faculty", faculty.get("username"), "Certification Updated", f"Certification '{cert.get('title', cert_id)}' updated by admin.")

    return jsonify({"message": "Certification updated", "certification": cert})


@research_bp.route("/faculty/<faculty_id>/certifications/<cert_id>", methods=["DELETE"])
@role_required("admin")
def delete_certification(faculty_id, cert_id):
    """Deletes a certification."""
    faculty_list = load_data(FACULTY_STORE)
    fac_idx, faculty = find_faculty(faculty_list, faculty_id)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    cert_idx, cert = find_cert(faculty, cert_id)
    if not cert:
        return jsonify({"error": "Certification not found"}), 404

    # Delete the associated file
    if cert.get("file"):
        delete_file(cert["file"])

    del faculty["certifications"][cert_idx]
    faculty_list[fac_idx] = faculty
    save_data(FACULTY_STORE, faculty_list)
    log_event("admin", "admin", "delete_certification", "faculty", faculty_id, {"cert_id": cert_id})
    push_notification("faculty", faculty.get("username"), "Certification Deleted", f"Certification '{cert.get('title', cert_id)}' deleted by admin.")

    return jsonify({"message": "Certification deleted"})


@research_bp.route("/faculty/<faculty_id>/certifications/<cert_id>/verify", methods=["POST"])
@role_required("admin")
def verify_certification(faculty_id, cert_id):
    """Toggles the verification status of a certification."""
    faculty_list = load_data(FACULTY_STORE)
    fac_idx, faculty = find_faculty(faculty_list, faculty_id)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    cert_idx, cert = find_cert(faculty, cert_id)
    if not cert:
        return jsonify({"error": "Certification not found"}), 404
        
    # Toggle status
    cert["verified"] = not cert.get("verified", False)
    
    faculty["certifications"][cert_idx] = cert
    faculty_list[fac_idx] = faculty
    save_data(FACULTY_STORE, faculty_list)
    log_event("admin", "admin", "verify_certification_toggle", "faculty", faculty_id, {"cert_id": cert_id, "verified": cert.get("verified")})
    push_notification("faculty", faculty.get("username"), "Certification Review Updated", f"Certification '{cert.get('title', cert_id)}' status: {'Verified' if cert.get('verified') else 'Pending'}.")

    return jsonify({"message": f"Certification status set to {cert['verified']}", "certification": cert})


# ======================================================
# BOOKS - ADMIN
# ======================================================
@research_bp.route("/faculty/<faculty_id>/books", methods=["POST"])
@role_required("admin")
def add_book(faculty_id):
    title = request.form.get("title")
    author = request.form.get("author", "")
    year = request.form.get("year", "")
    publisher = request.form.get("publisher", "")
    file = request.files.get("file")

    if not title:
        return jsonify({"error": "title is required"}), 400

    faculty_list = load_data(FACULTY_STORE)
    fac_idx, faculty = find_faculty(faculty_list, faculty_id)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    rel_path = ""
    if file and file.filename:
        rel_path = save_file(file, category="rd", faculty_id=faculty_id, tag=f"book_{title}")

    book = {
        "book_id": "book-" + uuid.uuid4().hex,
        "title": title,
        "author": author,
        "year": year,
        "publisher": publisher,
        "file": rel_path,
    }
    faculty.setdefault("books", []).append(book)
    faculty_list[fac_idx] = faculty
    save_data(FACULTY_STORE, faculty_list)
    log_event("admin", "admin", "add_book", "faculty", faculty_id, {"book_id": book.get("book_id")})
    push_notification("faculty", faculty.get("username"), "Book Added", f"Book '{title}' added by admin.")
    return jsonify({"message": "Book added", "book": book}), 201


@research_bp.route("/faculty/<faculty_id>/books/<book_id>", methods=["PUT"])
@role_required("admin")
def update_book(faculty_id, book_id):
    faculty_list = load_data(FACULTY_STORE)
    fac_idx, faculty = find_faculty(faculty_list, faculty_id)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    books = faculty.setdefault("books", [])
    book_idx, book = find_item(books, "book_id", book_id)
    if not book:
        return jsonify({"error": "Book not found"}), 404

    data = request.form if request.form else (request.json or {})
    book["title"] = data.get("title", book.get("title"))
    book["author"] = data.get("author", book.get("author"))
    book["year"] = data.get("year", book.get("year"))
    book["publisher"] = data.get("publisher", book.get("publisher"))

    file = request.files.get("file") if hasattr(request, "files") else None
    if file and file.filename:
        if book.get("file"):
            delete_file(book["file"])
        book["file"] = save_file(file, category="rd", faculty_id=faculty_id, tag=f"book_{book['title']}")

    books[book_idx] = book
    faculty["books"] = books
    faculty_list[fac_idx] = faculty
    save_data(FACULTY_STORE, faculty_list)
    log_event("admin", "admin", "update_book", "faculty", faculty_id, {"book_id": book_id})
    push_notification("faculty", faculty.get("username"), "Book Updated", f"Book '{book.get('title', book_id)}' updated by admin.")
    return jsonify({"message": "Book updated", "book": book})


@research_bp.route("/faculty/<faculty_id>/books/<book_id>", methods=["DELETE"])
@role_required("admin")
def delete_book(faculty_id, book_id):
    faculty_list = load_data(FACULTY_STORE)
    fac_idx, faculty = find_faculty(faculty_list, faculty_id)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    books = faculty.setdefault("books", [])
    book_idx, book = find_item(books, "book_id", book_id)
    if not book:
        return jsonify({"error": "Book not found"}), 404

    if book.get("file"):
        delete_file(book["file"])

    del books[book_idx]
    faculty["books"] = books
    faculty_list[fac_idx] = faculty
    save_data(FACULTY_STORE, faculty_list)
    log_event("admin", "admin", "delete_book", "faculty", faculty_id, {"book_id": book_id})
    push_notification("faculty", faculty.get("username"), "Book Deleted", f"Book '{book.get('title', book_id)}' deleted by admin.")
    return jsonify({"message": "Book deleted"})


# ======================================================
# RESEARCH PAPERS - ADMIN
# ======================================================
@research_bp.route("/faculty/<faculty_id>/papers", methods=["POST"])
@role_required("admin")
def add_research_paper(faculty_id):
    title = request.form.get("title")
    journal = request.form.get("journal", "")
    year = request.form.get("year", "")
    doi = request.form.get("doi", "")
    file = request.files.get("file")

    if not title:
        return jsonify({"error": "title is required"}), 400

    faculty_list = load_data(FACULTY_STORE)
    fac_idx, faculty = find_faculty(faculty_list, faculty_id)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    rel_path = ""
    if file and file.filename:
        rel_path = save_file(file, category="rd", faculty_id=faculty_id, tag=f"paper_{title}")

    paper = {
        "paper_id": "paper-" + uuid.uuid4().hex,
        "title": title,
        "journal": journal,
        "year": year,
        "doi": doi,
        "file": rel_path,
    }
    faculty.setdefault("research_papers", []).append(paper)
    faculty_list[fac_idx] = faculty
    save_data(FACULTY_STORE, faculty_list)
    log_event("admin", "admin", "add_research_paper", "faculty", faculty_id, {"paper_id": paper.get("paper_id")})
    push_notification("faculty", faculty.get("username"), "Research Paper Added", f"Research paper '{title}' added by admin.")
    return jsonify({"message": "Research paper added", "paper": paper}), 201


@research_bp.route("/faculty/<faculty_id>/papers/<paper_id>", methods=["PUT"])
@role_required("admin")
def update_research_paper(faculty_id, paper_id):
    faculty_list = load_data(FACULTY_STORE)
    fac_idx, faculty = find_faculty(faculty_list, faculty_id)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    papers = faculty.setdefault("research_papers", [])
    paper_idx, paper = find_item(papers, "paper_id", paper_id)
    if not paper:
        return jsonify({"error": "Research paper not found"}), 404

    data = request.form if request.form else (request.json or {})
    paper["title"] = data.get("title", paper.get("title"))
    paper["journal"] = data.get("journal", paper.get("journal"))
    paper["year"] = data.get("year", paper.get("year"))
    paper["doi"] = data.get("doi", paper.get("doi"))

    file = request.files.get("file") if hasattr(request, "files") else None
    if file and file.filename:
        if paper.get("file"):
            delete_file(paper["file"])
        paper["file"] = save_file(file, category="rd", faculty_id=faculty_id, tag=f"paper_{paper['title']}")

    papers[paper_idx] = paper
    faculty["research_papers"] = papers
    faculty_list[fac_idx] = faculty
    save_data(FACULTY_STORE, faculty_list)
    log_event("admin", "admin", "update_research_paper", "faculty", faculty_id, {"paper_id": paper_id})
    push_notification("faculty", faculty.get("username"), "Research Paper Updated", f"Research paper '{paper.get('title', paper_id)}' updated by admin.")
    return jsonify({"message": "Research paper updated", "paper": paper})


@research_bp.route("/faculty/<faculty_id>/papers/<paper_id>", methods=["DELETE"])
@role_required("admin")
def delete_research_paper(faculty_id, paper_id):
    faculty_list = load_data(FACULTY_STORE)
    fac_idx, faculty = find_faculty(faculty_list, faculty_id)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    papers = faculty.setdefault("research_papers", [])
    paper_idx, paper = find_item(papers, "paper_id", paper_id)
    if not paper:
        return jsonify({"error": "Research paper not found"}), 404

    if paper.get("file"):
        delete_file(paper["file"])

    del papers[paper_idx]
    faculty["research_papers"] = papers
    faculty_list[fac_idx] = faculty
    save_data(FACULTY_STORE, faculty_list)
    log_event("admin", "admin", "delete_research_paper", "faculty", faculty_id, {"paper_id": paper_id})
    push_notification("faculty", faculty.get("username"), "Research Paper Deleted", f"Research paper '{paper.get('title', paper_id)}' deleted by admin.")
    return jsonify({"message": "Research paper deleted"})
