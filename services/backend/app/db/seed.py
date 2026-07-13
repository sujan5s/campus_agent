"""Idempotent demo seed data — 1 dept (CSE), 2 sections, 6 teachers, 8 subjects, 8 rooms.

Runs automatically on server startup (skips if users already exist).
Demo logins:  admin@campus.edu / admin123
              anita.rao@campus.edu / faculty123   (faculty, HOD-ish)
              student@campus.edu / student123
"""
from datetime import time

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import Room, Section, Subject, Teacher, TimeSlot, User
from app.db.session import SessionLocal


def seed() -> bool:
    """Populate demo data. Returns True if seeding ran, False if already seeded."""
    db: Session = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return False

        # --- Users -----------------------------------------------------------
        admin = User(name="Campus Admin", email="admin@campus.edu", role="admin",
                     password_hash=hash_password("admin123"))
        db.add(admin)

        faculty_specs = [
            ("Dr. Anita Rao", "anita.rao@campus.edu"),
            ("Prof. Ravi Kumar", "ravi.kumar@campus.edu"),
            ("Dr. Meera Nair", "meera.nair@campus.edu"),
            ("Prof. Suresh Shetty", "suresh.shetty@campus.edu"),
            ("Dr. Kavya Hegde", "kavya.hegde@campus.edu"),
            ("Prof. Arjun Pai", "arjun.pai@campus.edu"),
        ]
        teachers: list[Teacher] = []
        for name, email in faculty_specs:
            u = User(name=name, email=email, role="faculty",
                     password_hash=hash_password("faculty123"))
            db.add(u)
            db.flush()
            t = Teacher(user_id=u.id, dept="CSE", max_hours_per_day=5)
            db.add(t)
            teachers.append(t)

        db.add(User(name="Demo Student", email="student@campus.edu", role="student",
                    password_hash=hash_password("student123")))

        # --- Sections ----------------------------------------------------------
        db.add_all([
            Section(name="CSE-7A", dept="CSE", semester=7, strength=60),
            Section(name="CSE-7B", dept="CSE", semester=7, strength=58),
        ])

        # --- Subjects (sem 7 CSE) ----------------------------------------------
        subject_specs = [
            ("CS701", "Artificial Intelligence", 4, False),
            ("CS702", "Distributed Systems", 4, False),
            ("CS703", "Machine Learning Lab", 2, True),
            ("CS704", "Cloud Computing", 3, False),
            ("CS705", "Compiler Design", 4, False),
            ("CS706", "Cyber Security", 3, False),
            ("CS707", "Big Data Lab", 2, True),
            ("CS708", "Project Phase I", 2, False),
        ]
        subjects: list[Subject] = []
        for code, name, ppw, lab in subject_specs:
            s = Subject(code=code, name=name, dept="CSE", semester=7,
                        periods_per_week=ppw, needs_lab=lab)
            db.add(s)
            subjects.append(s)
        db.flush()

        # Each teacher can teach 2-3 subjects (round-robin coverage)
        for i, t in enumerate(teachers):
            t.subjects = [subjects[i % 8], subjects[(i + 3) % 8], subjects[(i + 5) % 8]]

        # --- Rooms ---------------------------------------------------------------
        db.add_all([
            Room(name="LT-301", type="classroom", capacity=70),
            Room(name="LT-302", type="classroom", capacity=70),
            Room(name="LT-303", type="classroom", capacity=65),
            Room(name="CS Lab 1", type="lab", capacity=60),
            Room(name="CS Lab 2", type="lab", capacity=60),
            Room(name="Main Auditorium", type="auditorium", capacity=500),
            Room(name="Seminar Hall B", type="seminar", capacity=150),
            Room(name="Sports Ground", type="ground", capacity=1000),
        ])

        # --- Timeslots: MON-FRI × 7 periods --------------------------------------
        period_times = [
            (time(9, 0), time(9, 55)), (time(9, 55), time(10, 50)),
            (time(11, 10), time(12, 5)), (time(12, 5), time(13, 0)),
            (time(14, 0), time(14, 55)), (time(14, 55), time(15, 50)),
            (time(15, 50), time(16, 45)),
        ]
        for day in ["MON", "TUE", "WED", "THU", "FRI"]:
            for pno, (start, end) in enumerate(period_times, start=1):
                db.add(TimeSlot(day=day, period_no=pno, start=start, end=end))

        db.commit()
        return True
    finally:
        db.close()


if __name__ == "__main__":
    from app.db.session import init_db

    init_db()
    print("Seeded demo data." if seed() else "Already seeded — skipped.")
