"""Idempotent demo seed data — 1 dept (CSE), 2 sections, 6 teachers, 8 subjects, 8 rooms.

Runs automatically on server startup (skips if users already exist).
Demo logins:  admin@campus.edu / admin123
              anita.rao@campus.edu / faculty123   (faculty, HOD-ish)
              student@campus.edu / student123
"""
from datetime import time

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import (
    ElectiveGroup, ElectiveOffering, Room, Section, Subject, Teacher, TimeSlot,
    User,
)
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

        # --- Sections ----------------------------------------------------------
        sections = [
            Section(name="CSE-7A", dept="CSE", semester=7, strength=60),
            Section(name="CSE-7B", dept="CSE", semester=7, strength=58),
        ]
        db.add_all(sections)
        db.flush()

        # Attached to a real section so the booking agent can derive this
        # student's faculty advisor from the timetable (Phase 3, F3).
        db.add(User(name="Demo Student", email="student@campus.edu", role="student",
                    password_hash=hash_password("student123"),
                    section_id=sections[0].id))

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


# --- Phase 2.4 demo data ------------------------------------------------------
#
# Unlike seed() this runs on *every* startup and only adds what is missing, so a
# database seeded before Phase 2.4 gains the multi-semester and open-elective
# demo data without being wiped.

SEM5_SUBJECTS = [
    ("CS501", "Operating Systems", 4, False),
    ("CS502", "Computer Networks", 4, False),
    ("CS503", "Database Systems", 3, False),
    ("CS504", "Software Engineering", 3, False),
    ("CS505", "Networks Lab", 2, True),
]

# Open-elective baskets for semester 7 — parallel options during one shared band.
OPEN_ELECTIVES = [
    ("CS7OE1", "Blockchain Technology", "Seminar Hall B"),
    ("CS7OE2", "IoT & Edge Computing", "Main Auditorium"),
]


def seed_phase24() -> list[str]:
    """Add semester-5 data and a semester-7 open-elective band if absent.

    Idempotent: every step checks first, so restarting the server never
    duplicates a row. Returns a short log of what it created."""
    db: Session = SessionLocal()
    log: list[str] = []
    try:
        teachers = db.query(Teacher).order_by(Teacher.id).all()
        if not teachers:
            return log  # nothing seeded yet — seed() runs first

        # a fourth classroom keeps the home-room pool ahead of the section count
        if not db.query(Room).filter(Room.name == "LT-304").first():
            db.add(Room(name="LT-304", type="classroom", capacity=70))
            log.append("room LT-304")

        # --- semester 5: a second cohort whose week can be shaped differently ---
        sem5_subjects = []
        for i, (code, name, ppw, lab) in enumerate(SEM5_SUBJECTS):
            subj = db.query(Subject).filter(Subject.code == code).first()
            if not subj:
                subj = Subject(code=code, name=name, dept="CSE", semester=5,
                               periods_per_week=ppw, needs_lab=lab)
                db.add(subj)
                db.flush()
                log.append(f"subject {code}")
            sem5_subjects.append(subj)
        # spread them over the existing faculty (2 teachers can take each)
        for i, subj in enumerate(sem5_subjects):
            for t in (teachers[i % len(teachers)], teachers[(i + 2) % len(teachers)]):
                if subj not in t.subjects:
                    t.subjects.append(subj)

        if not db.query(Section).filter(Section.name == "CSE-5A").first():
            db.add(Section(name="CSE-5A", dept="CSE", semester=5, strength=62))
            log.append("section CSE-5A")

        # --- semester 7 open-elective band -------------------------------------
        if db.query(ElectiveGroup).filter(ElectiveGroup.semester == 7).first() is None:
            offerings = []
            for i, (code, name, room_name) in enumerate(OPEN_ELECTIVES):
                subj = db.query(Subject).filter(Subject.code == code).first()
                if not subj:
                    subj = Subject(code=code, name=name, dept="CSE", semester=7,
                                   periods_per_week=3, needs_lab=False)
                    db.add(subj)
                    db.flush()
                room = db.query(Room).filter(Room.name == room_name).first()
                teacher = teachers[i % len(teachers)]
                if subj not in teacher.subjects:
                    teacher.subjects.append(subj)
                if room:
                    offerings.append((subj, teacher, room))
            if offerings:
                group = ElectiveGroup(name="OE-1", dept="CSE", semester=7,
                                      periods_per_week=3, needs_block=False, active=True)
                db.add(group)
                db.flush()
                for subj, teacher, room in offerings:
                    db.add(ElectiveOffering(group_id=group.id, subject_id=subj.id,
                                            teacher_id=teacher.id, room_id=room.id,
                                            capacity=60))
                log.append(f"open-elective band OE-1 ({len(offerings)} options)")

        db.commit()
        return log
    finally:
        db.close()


if __name__ == "__main__":
    from app.db.session import init_db

    init_db()
    print("Seeded demo data." if seed() else "Already seeded — skipped.")
    extra = seed_phase24()
    print("Phase 2.4 data added: " + ", ".join(extra) if extra else "Phase 2.4 data present.")
