"""Timetable API — generation (admin) + grid views (any authenticated user)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.tools.timetable import (
    generate_timetable, get_section_grid, get_teacher_grid, latest_version,
)

router = APIRouter()


@router.post("/generate", dependencies=[Depends(require_role("admin"))])
def generate():
    """Run the CP-SAT solver on current master data. Stores a new version on success."""
    result = generate_timetable()
    if result["status"] in ("optimal", "feasible"):
        return result
    # infeasible / error → 422 with the precise reasons for the UI to display
    raise HTTPException(status_code=422, detail=result)


@router.get("/status")
def status(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {"latest_version": latest_version(db)}


@router.get("/section/{name}")
def section_grid(name: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    grid = get_section_grid(db, name)
    if "error" in grid:
        raise HTTPException(status_code=404, detail=grid["error"])
    return grid


@router.get("/teacher/{tid}")
def teacher_grid(tid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    grid = get_teacher_grid(db, tid)
    if "error" in grid:
        raise HTTPException(status_code=404, detail=grid["error"])
    return grid
