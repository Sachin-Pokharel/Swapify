from fastapi import APIRouter
from app.api.endpoints import health, face_swap


api_router = APIRouter()
api_router.include_router(face_swap.router, tags=['face_swap'])
api_router.include_router(health.router, tags=['health'])