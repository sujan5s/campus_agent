"""API aggregator — one sub-router per domain (docs/02-ARCHITECTURE.md §4).

main.py mounts this under /api. Add new domain routers here as phases land
(timetable, leaves, approvals, bookings, documents, notifications).
"""
from fastapi import APIRouter

from app.api import agent, auth

router = APIRouter()
router.include_router(agent.router, tags=["agent"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
