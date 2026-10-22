from fastapi import APIRouter

from app.api.v1.endpoints import (
    account,
    attempts,
    exercises,
    images,
    invites,
    skills,
    students,
    study_plans,
    subjects,
    teachers,
)

api_router = APIRouter()
api_router.include_router(account.router)
api_router.include_router(invites.router)
api_router.include_router(teachers.router)
api_router.include_router(students.router)
api_router.include_router(subjects.router)
api_router.include_router(exercises.router)
api_router.include_router(images.router)
api_router.include_router(study_plans.router)
api_router.include_router(attempts.router)
api_router.include_router(skills.router)
