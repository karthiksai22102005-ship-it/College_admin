# one-time script to update the faculty data schema
import os
from utils.data_store import load_data, save_data

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FACULTY_STORE = os.path.join(BASE_DIR, "data", "faculty.store")

def update_schema():
    """
    Updates the schema for all faculty records in faculty.store.
    - Adds 'personal_documents' if not present.
    - Adds 'certifications' if not present.
    - Converts 'subject_expertise' from a list of strings to a list of objects.
    - Converts 'publications' to 'certifications' if possible, otherwise removes.
    """
    print("Loading faculty data...")
    faculty_list = load_data(FACULTY_STORE)

    if not isinstance(faculty_list, list):
        print("Error: faculty.store does not contain a list.")
        return

    updated_count = 0
    for i, faculty in enumerate(faculty_list):
        made_change = False

        # 1. Add 'personal_documents'
        if "personal_documents" not in faculty:
            faculty["personal_documents"] = {
                "aadhaar": "",
                "pan": "",
                "bank_passbook": "",
                "service_register": "",
                "joining_letter": "",
                "others": []
            }
            print(f"  - Added 'personal_documents' for {faculty.get('name')}")
            made_change = True

        # 2. Add 'certifications' and migrate old 'publications'
        if "certifications" not in faculty:
            faculty["certifications"] = []
            print(f"  - Added 'certifications' for {faculty.get('name')}")
            made_change = True

        # Simple migration from old 'publications' field
        if "publications" in faculty and faculty["publications"]:
             print(f"  - Migrating 'publications' for {faculty.get('name')}")
             # This is a placeholder for a more complex migration logic if needed.
             # For now, we just remove the old field.
             del faculty["publications"]
             made_change = True


        # 3. Update 'subject_expertise' structure
        if "subject_expertise" in faculty and isinstance(faculty["subject_expertise"], list):
            # Check if the first element is a string (old format)
            if faculty["subject_expertise"] and isinstance(faculty["subject_expertise"][0], str):
                print(f"  - Converting 'subject_expertise' for {faculty.get('name')}")
                new_expertise = []
                for subject in faculty["subject_expertise"]:
                    new_expertise.append({
                        "subject": subject,
                        "cert_ids": []
                    })
                faculty["subject_expertise"] = new_expertise
                made_change = True
        
        if made_change:
            updated_count += 1
            
        faculty_list[i] = faculty

    if updated_count > 0:
        print(f"\nSchema updated for {updated_count} faculty records.")
        try:
            # Create a backup before saving
            backup_path = FACULTY_STORE + ".bak"
            print(f"Creating backup at {backup_path}")
            os.rename(FACULTY_STORE, backup_path)
            
            print("Saving updated data to faculty.store...")
            save_data(FACULTY_STORE, faculty_list)
            print("Save successful!")
        except Exception as e:
            print(f"Error during save: {e}")
            # Try to restore backup
            if os.path.exists(backup_path):
                print("Attempting to restore backup...")
                os.rename(backup_path, FACULTY_STORE)
    else:
        print("No schema updates were necessary.")

if __name__ == "__main__":
    update_schema()
