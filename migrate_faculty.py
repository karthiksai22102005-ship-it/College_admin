import os
import sys
import math
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from utils.data_store import load_data, save_data

FACULTY_STORE = os.path.join(BASE_DIR, "data", "faculty.store")

def migrate_aiml_to_aids():
    """
    A one-time script to move half of the faculty from the AIML department
    to the AIDS department.
    """
    print("🔄 Starting faculty migration...")
    try:
        faculty_list = load_data(FACULTY_STORE)
        if not isinstance(faculty_list, list):
            print("❌ Error: faculty.store does not contain a list of faculty.")
            return

        # Create a backup before making any changes
        backup_path = FACULTY_STORE + ".bak"
        print(f"Creating a backup of your data at {backup_path}...")
        shutil.copy(FACULTY_STORE, backup_path)
        print("Backup created successfully.")

        # Find all faculty in the 'AIML' department
        aiml_faculty = [f for f in faculty_list if f.get("department") == "AIML"]

        if not aiml_faculty:
            print("✅ No faculty found in AIML department. No migration needed.")
            return

        # Calculate half to move (rounding up)
        num_to_move = math.ceil(len(aiml_faculty) / 2)
        faculty_to_move_ids = {f['faculty_id'] for f in aiml_faculty[:num_to_move]}

        print(f"Found {len(aiml_faculty)} faculty in AIML. Moving {len(faculty_to_move_ids)} to AIDS.")

        # Update the department for the selected faculty
        for faculty in faculty_list:
            if faculty.get("faculty_id") in faculty_to_move_ids:
                print(f"  -> Moving '{faculty.get('name')}' to AIDS department.")
                faculty["department"] = "AIDS"

        save_data(FACULTY_STORE, faculty_list)
        print("\n✅ Successfully saved updated faculty data. Migration complete!")

    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    migrate_aiml_to_aids()
