"""
Master Router Package combining Common, Flights, Stays, and Cars sub-routers.
"""

from fastapi import APIRouter

from .bundles import router as bundles_router
from .cars import router as cars_router
from .common import (
    create_card_endpoint,
    create_component_client_key_endpoint,
    create_three_d_secure_session_endpoint,
    get_api_help,
    get_duffel_client,
    get_supported_payment_methods,
    health_check,
)
from .common import (
    router as common_router,
)
from .flights import (
    analyze_candidate_queries,
    book_flight,
    get_flight_offer_details,
    get_search_exact_flights,
    get_search_result_file,
    pay_hold_order,
    search_exact_flights,
    search_natural_language_flights,
    search_optimized_flights,
)
from .flights import (
    router as flights_router,
)
from .ai_search import router as ai_search_router
from .natural_search import router as natural_search_router
from .places import router as places_router
from .planner import router as planner_router
from .stays import router as stays_router

# Assembles main APIRouter containing all domain submodules
router = APIRouter(tags=["Duffel REST API"])
router.include_router(common_router)
router.include_router(ai_search_router)
router.include_router(natural_search_router)
router.include_router(flights_router)
router.include_router(stays_router)
router.include_router(cars_router)
router.include_router(bundles_router)
router.include_router(planner_router)
router.include_router(places_router)



__all__ = [
    "router",
    "get_duffel_client",
    "health_check",
    "get_api_help",
    "get_supported_payment_methods",
    "create_component_client_key_endpoint",
    "create_three_d_secure_session_endpoint",
    "create_card_endpoint",
    "analyze_candidate_queries",
    "search_optimized_flights",
    "search_exact_flights",
    "get_search_exact_flights",
    "search_natural_language_flights",
    "get_search_result_file",
    "get_flight_offer_details",
    "book_flight",
    "pay_hold_order",
]
