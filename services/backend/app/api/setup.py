"""Data Setup API — CRUD + CSV import for the academic master data
(subjects, teachers, sections, rooms). This is how timetable data enters the
system (docs/02-ARCHITECTURE.md): admin forms/CSV -> DB; agents then read the
DB via tools. Reads are open to any authenticated user; writes are admin-only.
"""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user, hash_password, require_role
from app.db.models import Room, Section, Subject, Teacher, User
from app.db.session import get_db

router = APIRouter()

admin_only = Depends(require_role("admin"))
any_user = Depends(get_current_user)


# ---------- Schemas ----------

class SubjectIn(BaseModel):
    code: str
    name: str
    dept: str = "CSE"
    semester: int = 7
    periods_per_week: int = 4
    needs_lab: bool = False


class SubjectOut(SubjectIn):
    id: int

    class Config:
        from_attributes = True


class SectionIn(BaseModel):
    name: str
    dept: str = "CSE"
    semester: int = 7
    strength: int = 60


class SectionOut(SectionIn):
    id: int

    class Config:
        from_attributes = True


class RoomIn(BaseModel):
    name: str
    type: str = "classroom"  # classroom | lab | auditorium | seminar | ground
    capacity: int = 60


class RoomOut(RoomIn):
    id: int

    class Config:
        from_attributes = True


class TeacherIn(BaseModel):
    name: str
    email: str
    dept: str = "CSE"
    max_hours_per_day: int = 5
    subject_ids: list[int] = []


class TeacherOut(BaseModel):
    id: int
    name: str
    email: str
    dept: str
    max_hours_per_day: int
    subject_ids: list[int]
    subject_codes: list[str]


def _teacher_out(t: Teacher) -> TeacherOut:
    return TeacherOut(
        id=t.id, name=t.user.name, email=t.user.email, dept=t.dept,
        max_hours_per_day=t.max_hours_per_day,
        subject_ids=[s.id for s in t.subjects],
        subject_codes=[s.code for s in t.subjects],
    )


# ---------- Subjects ----------

@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(db: Session = Depends(get_db), user=any_user):
    return db.query(Subject).order_by(Subject.code).all()


@router.post("/subjects", response_model=SubjectOut, dependencies=[admin_only])
def create_subject(payload: SubjectIn, db: Session = Depends(get_db)):
    if db.query(Subject).filter(Subject.code == payload.code).first():
        raise HTTPException(409, f"Subject code '{payload.code}' already exists")
    s = Subject(**payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.put("/subjects/{sid}", response_model=SubjectOut, dependencies=[admin_only])
def update_subject(sid: int, payload: SubjectIn, db: Session = Depends(get_db)):
    s = db.get(Subject, sid)
    if not s:
        raise HTTPException(404, "Subject not found")
    for k, v in payload.model_dump().items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/subjects/{sid}", dependencies=[admin_only])
def delete_subject(sid: int, db: Session = Depends(get_db)):
    s = db.get(Subject, sid)
    if not s:
        raise HTTPException(404, "Subject not found")
    s.teachers = []
    db.delete(s)
    db.commit()
    return {"deleted": sid}


# ---------- Sections ----------

@router.get("/sections", response_model=list[SectionOut])
def list_sections(db: Session = Depends(get_db), user=any_user):
    return db.query(Section).order_by(Section.name).all()


@router.post("/sections", response_model=SectionOut, dependencies=[admin_only])
def create_section(payload: SectionIn, db: Session = Depends(get_db)):
    if db.query(Section).filter(Section.name == payload.name).first():
        raise HTTPException(409, f"Section '{payload.name}' already exists")
    s = Section(**payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.put("/sections/{sid}", response_model=SectionOut, dependencies=[admin_only])
def update_section(sid: int, payload: SectionIn, db: Session = Depends(get_db)):
    s = db.get(Section, sid)
    if not s:
        raise HTTPException(404, "Section not found")
    for k, v in payload.model_dump().items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/sections/{sid}", dependencies=[admin_only])
def delete_section(sid: int, db: Session = Depends(get_db)):
    s = db.get(Section, sid)
    if not s:
        raise HTTPException(404, "Section not found")
    db.delete(s)
    db.commit()
    return {"deleted": sid}


# ---------- Rooms ----------

ROOM_TYPES = {"classroom", "lab", "auditorium", "seminar", "ground"}


@router.get("/rooms", response_model=list[RoomOut])
def list_rooms(db: Session = Depends(get_db), user=any_user):
    return db.query(Room).order_by(Room.name).all()


@router.post("/rooms", response_model=RoomOut, dependencies=[admin_only])
def create_room(payload: RoomIn, db: Session = Depends(get_db)):
    if payload.type not in ROOM_TYPES:
        raise HTTPException(422, f"type must be one of {sorted(ROOM_TYPES)}")
    if db.query(Room).filter(Room.name == payload.name).first():
        raise HTTPException(409, f"Room '{payload.name}' already exists")
    r = Room(**payload.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@router.put("/rooms/{rid}", response_model=RoomOut, dependencies=[admin_only])
def update_room(rid: int, payload: RoomIn, db: Session = Depends(get_db)):
    r = db.get(Room, rid)
    if not r:
        raise HTTPException(404, "Room not found")
    if payload.type not in ROOM_TYPES:
        raise HTTPException(422, f"type must be one of {sorted(ROOM_TYPES)}")
    for k, v in payload.model_dump().items():
        setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return r


@router.delete("/rooms/{rid}", dependencies=[admin_only])
def delete_room(rid: int, db: Session = Depends(get_db)):
    r = db.get(Room, rid)
    if not r:
        raise HTTPException(404, "Room not found")
    db.delete(r)
    db.commit()
    return {"deleted": rid}


# ---------- Teachers ----------

@router.get("/teachers", response_model=list[TeacherOut])
def list_teachers(db: Session = Depends(get_db), user=any_user):
    return [_teacher_out(t) for t in db.query(Teacher).all()]


@router.post("/teachers", response_model=TeacherOut, dependencies=[admin_only])
def create_teacher(payload: TeacherIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(409, f"User email '{payload.email}' already exists")
    u = User(name=payload.name, email=payload.email, role="faculty",
             password_hash=hash_password("faculty123"))  # default; teacher changes later
    db.add(u)
    db.flush()
    t = Teacher(user_id=u.id, dept=payload.dept, max_hours_per_day=payload.max_hours_per_day)
    t.subjects = db.query(Subject).filter(Subject.id.in_(payload.subject_ids)).all()
    db.add(t)
    db.commit()
    db.refresh(t)
    return _teacher_out(t)


@router.put("/teachers/{tid}", response_model=TeacherOut, dependencies=[admin_only])
def update_teacher(tid: int, payload: TeacherIn, db: Session = Depends(get_db)):
    t = db.get(Teacher, tid)
    if not t:
        raise HTTPException(404, "Teacher not found")
    t.user.name = payload.name
    t.user.email = payload.email
    t.dept = payload.dept
    t.max_hours_per_day = payload.max_hours_per_day
    t.subjects = db.query(Subject).filter(Subject.id.in_(payload.subject_ids)).all()
    db.commit()
    db.refresh(t)
    return _teacher_out(t)


@router.delete("/teachers/{tid}", dependencies=[admin_only])
def delete_teacher(tid: int, db: Session = Depends(get_db)):
    t = db.get(Teacher, tid)
    if not t:
        raise HTTPException(404, "Teacher not found")
    t.subjects = []
    user = t.user
    db.delete(t)
    if user:
        db.delete(user)
    db.commit()
    return {"deleted": tid}


# ---------- CSV import ----------
#
# Templates (header row required; see /setup page for downloads):
#   subjects.csv : code,name,dept,semester,periods_per_week,needs_lab
#   teachers.csv : name,email,dept,max_hours_per_day,subject_codes   (codes ;-separated)
#   sections.csv : name,dept,semester,strength
#   rooms.csv    : name,type,capacity

@router.post("/import/{entity}", dependencies=[admin_only])
async def import_csv(entity: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if entity not in {"subjects", "teachers", "sections", "rooms"}:
        raise HTTPException(404, "entity must be subjects | teachers | sections | rooms")

    raw = (await file.read()).decode("utf-8-sig")  # utf-8-sig: tolerate Excel BOM
    rows = list(csv.DictReader(io.StringIO(raw)))
    if not rows:
        raise HTTPException(422, "CSV is empty or has no header row")

    created, updated, errors = 0, 0, []
    for i, row in enumerate(rows, start=2):  # start=2: header is line 1
        try:
            row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            if entity == "subjects":
                existing = db.query(Subject).filter(Subject.code == row["code"]).first()
                vals = dict(
                    code=row["code"], name=row["name"], dept=row.get("dept", "CSE"),
                    semester=int(row.get("semester", 7)),
                    periods_per_week=int(row.get("periods_per_week", 4)),
                    needs_lab=row.get("needs_lab", "false").lower() in ("1", "true", "yes"),
                )
            elif entity == "sections":
                existing = db.query(Section).filter(Section.name == row["name"]).first()
                vals = dict(name=row["name"], dept=row.get("dept", "CSE"),
                            semester=int(row.get("semester", 7)),
                            strength=int(row.get("strength", 60)))
            elif entity == "rooms":
                if row.get("type", "classroom") not in ROOM_TYPES:
                    raise ValueError(f"invalid type '{row.get('type')}'")
                existing = db.query(Room).filter(Room.name == row["name"]).first()
                vals = dict(name=row["name"], type=row.get("type", "classroom"),
                            capacity=int(row.get("capacity", 60)))
            else:  # teachers
                codes = [c.strip() for c in row.get("subject_codes", "").split(";") if c.strip()]
                subjects = db.query(Subject).filter(Subject.code.in_(codes)).all() if codes else []
                found = {s.code for s in subjects}
                missing = [c for c in codes if c not in found]
                if missing:
                    raise ValueError(f"unknown subject codes: {missing}")
                u = db.query(User).filter(User.email == row["email"]).first()
                if u and u.teacher:
                    t = u.teacher
                    u.name = row["name"]
                    t.dept = row.get("dept", "CSE")
                    t.max_hours_per_day = int(row.get("max_hours_per_day", 5))
                    t.subjects = subjects
                    updated += 1
                elif u:
                    raise ValueError(f"email '{row['email']}' belongs to a non-teacher user")
                else:
                    u = User(name=row["name"], email=row["email"], role="faculty",
                             password_hash=hash_password("faculty123"))
                    db.add(u)
                    db.flush()
                    t = Teacher(user_id=u.id, dept=row.get("dept", "CSE"),
                                max_hours_per_day=int(row.get("max_hours_per_day", 5)))
                    t.subjects = subjects
                    db.add(t)
                    created += 1
                continue

            # generic upsert for subjects / sections / rooms
            if existing:
                for k, v in vals.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                model = {"subjects": Subject, "sections": Section, "rooms": Room}[entity]
                db.add(model(**vals))
                created += 1
        except (KeyError, ValueError, TypeError) as e:
            errors.append(f"line {i}: {e}")

    if errors and not (created or updated):
        db.rollback()
        raise HTTPException(422, "; ".join(errors[:5]))
    db.commit()
    return {"created": created, "updated": updated, "errors": errors}
