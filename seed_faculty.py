#!/usr/bin/env python3
"""
Seed test faculty with login credentials for testing
"""
from utils.data_store import load_data, save_data

def seed_faculty():
    faculty_list = load_data("data/faculty.store")
    
    # Check if already seeded
    if len(faculty_list) > 0:
        print(f"Faculty data already exists ({len(faculty_list)} records). Skip seeding? (y/n)")
        return
    
    # Test Faculty with credentials
    test_faculty = [
        {
            "faculty_id": "FAC001",
            "name": "Dr. Rajesh Kumar",
            "department": "CSE",
            "designation": "Professor",
            "email": "rajesh@college.edu",
            "phone": "9876543210",
            "username": "rajesh",
            "password": "raj@123",
            "photo": "",
            "qualifications": [
                {"type": "B.Tech", "year": "2010"},
                {"type": "PhD", "year": "2015"}
            ],
            "subject_expertise": ["Data Structures", "Algorithms", "Database Design"],
            "publications": [
                {"type": "Scopus", "details": "Published 5 papers on AI"},
                {"type": "ResearchGate", "details": "Active researcher in ML"}
            ]
        },
        {
            "faculty_id": "FAC002",
            "name": "Dr. Priya Sharma",
            "department": "ECE",
            "designation": "Associate Professor",
            "email": "priya@college.edu",
            "phone": "9876543211",
            "username": "priya",
            "password": "priya@123",
            "photo": "",
            "qualifications": [
                {"type": "B.Tech", "year": "2012"},
                {"type": "M.Tech", "year": "2014"}
            ],
            "subject_expertise": ["Digital Signal Processing", "Microcontrollers"],
            "publications": [
                {"type": "ORCID", "details": "ORCID: 0000-0000-0000-0001"},
                {"type": "Books", "details": "1 book on embedded systems"}
            ]
        },
        {
            "faculty_id": "FAC003",
            "name": "Dr. Amit Patel",
            "department": "AI and ML",
            "designation": "Assistant Professor",
            "email": "amit@college.edu",
            "phone": "9876543212",
            "username": "amit",
            "password": "amit@123",
            "photo": "",
            "qualifications": [
                {"type": "B.Tech", "year": "2015"},
                {"type": "MBA", "year": "2018"}
            ],
            "subject_expertise": ["Machine Learning", "Deep Learning", "TensorFlow"],
            "publications": [
                {"type": "ResearchGate", "details": "10+ publications on ML"},
                {"type": "Other", "details": "AI ethics consultant"}
            ]
        },
        {
            "faculty_id": "FAC004",
            "name": "Ms. Neha Singh",
            "department": "Mech",
            "designation": "Lecturer",
            "email": "neha@college.edu",
            "phone": "9876543213",
            "username": "neha",
            "password": "neha@123",
            "photo": "",
            "qualifications": [
                {"type": "B.Tech", "year": "2018"},
                {"type": "M.Tech", "year": "2020"}
            ],
            "subject_expertise": ["Thermodynamics", "CAD", "Manufacturing"],
            "publications": []
        },
        {
            "faculty_id": "FAC005",
            "name": "Mr. Vikram Desai",
            "department": "Civil",
            "designation": "Senior Lecturer",
            "email": "vikram@college.edu",
            "phone": "9876543214",
            "username": "vikram",
            "password": "vikram@123",
            "photo": "",
            "qualifications": [
                {"type": "B.Tech", "year": "2014"},
                {"type": "M.Tech", "year": "2016"}
            ],
            "subject_expertise": ["Structural Analysis", "RCC Design", "Construction Management"],
            "publications": [
                {"type": "Scopus", "details": "3 papers on sustainable construction"}
            ]
        }
    ]
    
    faculty_list.extend(test_faculty)
    save_data("data/faculty.store", faculty_list)
    
    print("✓ Test faculty seeded successfully!")
    print("\n📋 TEST FACULTY CREDENTIALS:\n")
    for fac in test_faculty:
        print(f"  Name: {fac['name']}")
        print(f"  Department: {fac['department']}")
        print(f"  Username: {fac['username']}")
        print(f"  Password: {fac['password']}")
        print()

if __name__ == "__main__":
    seed_faculty()
