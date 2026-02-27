from flask import Blueprint, request, jsonify, current_app
from utils.data_store import load_data, save_data
from utils.guards import role_required
from utils.file_handler import save_file, delete_file
from utils.audit_service import log_event
from utils.notification_service import push_notification
import os

personal_bp = Blueprint("personal_bp", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACULTY_STORE = os.path.join(BASE_DIR, "data", "faculty.store")

@personal_bp.route("/<faculty_id>", methods=["GET"])
@role_required("admin")
def get_personal_docs(faculty_id):
    """Gets the personal document status for a single faculty."""
    faculty_list = load_data(FACULTY_STORE)
    faculty = next((f for f in faculty_list if f.get("faculty_id") == faculty_id), None)
    
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404
        
    return jsonify(faculty.get("personal_documents", {}))


@personal_bp.route("/<faculty_id>/upload", methods=["POST"])
@role_required("admin")
def upload_personal_doc(faculty_id):
    """Handles uploading/replacing a personal document."""
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files["file"]
    doc_type = request.form.get("doc_type") # e.g., 'aadhaar', 'pan', 'others'

    if not doc_type:
        return jsonify({"error": "doc_type not specified"}), 400

    try:
        # Save the new file
        rel_path = save_file(file, category="personal", faculty_id=faculty_id, tag=doc_type)

        # Update the faculty record
        faculty_list = load_data(FACULTY_STORE)
        faculty_found = False
        for fac in faculty_list:
            if fac.get("faculty_id") == faculty_id:
                faculty_found = True
                
                # Ensure personal_documents object exists
                if "personal_documents" not in fac:
                    fac["personal_documents"] = {}

                # For 'others', append to the list. For others, replace.
                if doc_type == "others":
                    if "others" not in fac["personal_documents"]:
                        fac["personal_documents"]["others"] = []
                    fac["personal_documents"]["others"].append(rel_path)
                else:
                    # If replacing, delete the old file first
                    old_path = fac["personal_documents"].get(doc_type)
                    if old_path:
                        delete_file(old_path)
                    fac["personal_documents"][doc_type] = rel_path
                
                break
        
        if not faculty_found:
            return jsonify({"error": "Faculty not found"}), 404

        save_data(FACULTY_STORE, faculty_list)
        fac = next((f for f in faculty_list if f.get("faculty_id") == faculty_id), {})
        log_event("admin", "admin", "upload_personal_doc", "faculty", faculty_id, {"doc_type": doc_type})
        push_notification("faculty", fac.get("username"), "Personal Document Updated", f"{doc_type} uploaded by admin.")
        
        return jsonify({
            "message": "File uploaded successfully", 
            "path": rel_path,
            "personal_documents": next(f.get("personal_documents", {}) for f in faculty_list if f.get("faculty_id") == faculty_id)
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error uploading personal doc: {e}")
        return jsonify({"error": "An internal error occurred"}), 500


@personal_bp.route("/<faculty_id>/delete", methods=["POST"])
@role_required("admin")
def delete_personal_doc(faculty_id):
    """Deletes a personal document."""
    data = request.json
    doc_type = data.get("doc_type")
    path_to_delete = data.get("path") # Required for 'others'

    if not doc_type:
        return jsonify({"error": "doc_type not specified"}), 400
    
    faculty_list = load_data(FACULTY_STORE)
    faculty_found = False
    
    for fac in faculty_list:
        if fac.get("faculty_id") == faculty_id:
            faculty_found = True
            
            if "personal_documents" not in fac:
                return jsonify({"error": "No documents found for this faculty"}), 404

            if doc_type == "others":
                if not path_to_delete:
                    return jsonify({"error": "'path' is required for deleting 'others' docs"}), 400
                
                # Delete the file and remove from list
                if path_to_delete in fac["personal_documents"].get("others", []):
                    if delete_file(path_to_delete):
                        fac["personal_documents"]["others"].remove(path_to_delete)
                    else:
                        return jsonify({"error": "Failed to delete file from storage"}), 500
                else:
                    return jsonify({"error": "Document path not found in 'others' list"}), 404
            else:
                # For fixed doc types, get path from record
                path_to_delete = fac["personal_documents"].get(doc_type)
                if not path_to_delete:
                    return jsonify({"error": "No document found for this type"}), 404

                # Delete file and clear path from record
                if delete_file(path_to_delete):
                    fac["personal_documents"][doc_type] = ""
                else:
                    return jsonify({"error": "Failed to delete file from storage"}), 500
            
            break

    if not faculty_found:
        return jsonify({"error": "Faculty not found"}), 404

    save_data(FACULTY_STORE, faculty_list)
    fac = next((f for f in faculty_list if f.get("faculty_id") == faculty_id), {})
    log_event("admin", "admin", "delete_personal_doc", "faculty", faculty_id, {"doc_type": doc_type})
    push_notification("faculty", fac.get("username"), "Personal Document Removed", f"{doc_type} removed by admin.")
    
    return jsonify({
        "message": "Document deleted successfully",
        "personal_documents": next(f.get("personal_documents", {}) for f in faculty_list if f.get("faculty_id") == faculty_id)
    })
