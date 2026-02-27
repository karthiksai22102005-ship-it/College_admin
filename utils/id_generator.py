import uuid


def generate_faculty_id():
    return "FAC-" + uuid.uuid4().hex[:6].upper()


def generate_user_id():
    return "USR-" + uuid.uuid4().hex[:6].upper()
