"""SQLAlchemy models — mirrors the data model in docs/02-ARCHITECTURE.md §3."""
from datetime import date, datetime, time, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Table, Text, Time, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- People & auth ---------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(20))  # admin | faculty | student
    password_hash: Mapped[str] = mapped_column(String(300))
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id"), nullable=True)

    teacher: Mapped["Teacher | None"] = relationship(back_populates="user", uselist=False)


teacher_subjects = Table(
    "teacher_subjects",
    Base.metadata,
    Column("teacher_id", ForeignKey("teachers.id"), primary_key=True),
    Column("subject_id", ForeignKey("subjects.id"), primary_key=True),
)


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    dept: Mapped[str] = mapped_column(String(50))
    max_hours_per_day: Mapped[int] = mapped_column(Integer, default=5)

    user: Mapped[User] = relationship(back_populates="teacher")
    subjects: Mapped[list["Subject"]] = relationship(secondary=teacher_subjects, back_populates="teachers")


# --- Academic structure -----------------------------------------------------

class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    dept: Mapped[str] = mapped_column(String(50))
    semester: Mapped[int] = mapped_column(Integer)
    periods_per_week: Mapped[int] = mapped_column(Integer, default=4)
    needs_lab: Mapped[bool] = mapped_column(Boolean, default=False)

    teachers: Mapped[list[Teacher]] = relationship(secondary=teacher_subjects, back_populates="subjects")


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True)  # e.g. "CSE-7A"
    dept: Mapped[str] = mapped_column(String(50))
    semester: Mapped[int] = mapped_column(Integer)
    strength: Mapped[int] = mapped_column(Integer, default=60)


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    type: Mapped[str] = mapped_column(String(20))  # classroom | lab | auditorium | seminar | ground
    capacity: Mapped[int] = mapped_column(Integer)


class TimeSlot(Base):
    __tablename__ = "timeslots"

    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[str] = mapped_column(String(3))  # MON..FRI
    period_no: Mapped[int] = mapped_column(Integer)
    start: Mapped[time] = mapped_column(Time)
    end: Mapped[time] = mapped_column(Time)


class TimetableEntry(Base):
    __tablename__ = "timetable_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    timeslot_id: Mapped[int] = mapped_column(ForeignKey("timeslots.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | substituted | cancelled
    version: Mapped[int] = mapped_column(Integer, default=1)

    section: Mapped[Section] = relationship()
    subject: Mapped[Subject] = relationship()
    teacher: Mapped[Teacher] = relationship()
    room: Mapped[Room] = relationship()
    timeslot: Mapped[TimeSlot] = relationship()


# --- Leave & substitution (Phase 2) -----------------------------------------

class Leave(Base):
    __tablename__ = "leaves"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    from_date: Mapped[date] = mapped_column(Date)
    to_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | approved | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Substitution(Base):
    __tablename__ = "substitutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    timetable_entry_id: Mapped[int] = mapped_column(ForeignKey("timetable_entries.id"))
    date: Mapped[date] = mapped_column(Date)
    original_teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    substitute_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="proposed")  # proposed | approved | rejected
    plan_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # groups one agent plan


# --- Events & bookings (Phase 3) ---------------------------------------------

class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    organizer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    description: Mapped[str] = mapped_column(Text, default="")
    expected_headcount: Mapped[int] = mapped_column(Integer, default=0)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    date: Mapped[date] = mapped_column(Date)
    start: Mapped[time] = mapped_column(Time)
    end: Mapped[time] = mapped_column(Time)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected|cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    room: Mapped[Room] = relationship()


# --- Workflow plumbing --------------------------------------------------------

class Approval(Base):
    """Human-in-the-loop record. langgraph_thread_id resumes the paused graph."""

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))  # leave | substitution_plan | booking
    ref_id: Mapped[int] = mapped_column(Integer)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    langgraph_thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Document(Base):
    """RAG corpus registry (Phase 3)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    file_path: Mapped[str] = mapped_column(String(500))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    channel: Mapped[str] = mapped_column(String(20), default="in_app")
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
