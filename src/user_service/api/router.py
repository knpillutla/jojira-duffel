"""
Master API Router for Jojira User Service.
"""

from fastapi import APIRouter
from .routes.auth import router as auth_router
from .routes.profile import router as profile_router
from .routes.history import router as history_router
from .routes.trip_plans import router as trip_plans_router
from .routes.booked_itineraries import router as booked_itineraries_router

from .routes.user_preferences import router as user_preferences_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(user_preferences_router)
api_router.include_router(trip_plans_router)
api_router.include_router(booked_itineraries_router)
api_router.include_router(history_router)



