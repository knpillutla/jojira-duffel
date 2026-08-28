"""
Pydantic schemas package re-exporting all DTOs for Duffel REST API.
"""

from .bundles import (
    BundleBookingRequest,
    BundleBookingResponse,
    BundleCategoryHighlights,
    BundleItem,
    BundleSearchRequest,
    BundleSearchResponse,
)
from .cars import (
    CarBookingRequest,
    CarBookingResponse,
    CarSearchRequest,
    CarSearchResponse,
    DriverInput,
)
from .common import (
    ApiEndpointHelp,
    ApiHelpResponse,
    ComponentClientKeyResponse,
    HealthCheckResponse,
    OrderPaymentRequest,
    PassengerInput,
    PaymentInput,
    PaymentMethodOption,
    PaymentMethodsResponse,
)
from .flights import (
    AnalyzeQueriesResponse,
    FlightBookingRequest,
    FlightBookingResponse,
    FlightOfferSummary,
    NaturalLanguageFlightSearchRequest,
    OptimizedFlightSearchRequest,
    OptimizedFlightSearchResponse,
    StandardFlightSearchRequest,
)
from .ai_search import (
    AIBookingRequest,
    AIBookingResponse,
    AISearchRequest,
    AISearchResponse,
    SaveAISearchHistoryRequest,
    SaveAISearchHistoryResponse,
    AISearchHistoryItem,
    AISearchHistoryListResponse,
)
from .natural_search import (
    NaturalSearchMeta,
    NaturalSearchRequest,
    NaturalSearchResponse,
)
from .planner import (
    GeoLocation,
    ItineraryActivity,
    ItineraryDay,
    ItineraryPlannerRequest,
    ItineraryPlannerResponse,
)
from .prompts import (
    PopularPromptItem,
    PopularPromptsResponse,
)
from .stays import (
    GuestInput,
    StayBookingRequest,
    StayBookingResponse,
    StaySearchRequest,
    StaySearchResponse,
)

__all__ = [
    "PassengerInput",
    "PaymentInput",
    "OrderPaymentRequest",
    "HealthCheckResponse",
    "PaymentMethodOption",
    "PaymentMethodsResponse",
    "ComponentClientKeyResponse",
    "ApiEndpointHelp",
    "ApiHelpResponse",
    "StandardFlightSearchRequest",
    "OptimizedFlightSearchRequest",
    "NaturalLanguageFlightSearchRequest",
    "FlightBookingRequest",
    "FlightBookingResponse",
    "AnalyzeQueriesResponse",
    "FlightOfferSummary",
    "OptimizedFlightSearchResponse",
    "GuestInput",
    "StaySearchRequest",
    "StaySearchResponse",
    "StayBookingRequest",
    "StayBookingResponse",
    "DriverInput",
    "CarSearchRequest",
    "CarSearchResponse",
    "CarBookingRequest",
    "CarBookingResponse",
    "BundleSearchRequest",
    "BundleSearchResponse",
    "BundleItem",
    "BundleCategoryHighlights",
    "BundleBookingRequest",
    "BundleBookingResponse",
    "GeoLocation",
    "ItineraryActivity",
    "ItineraryDay",
    "ItineraryPlannerRequest",
    "ItineraryPlannerResponse",
    "NaturalSearchRequest",
    "NaturalSearchMeta",
    "NaturalSearchResponse",
    "AISearchRequest",
    "AISearchResponse",
    "AIBookingRequest",
    "AIBookingResponse",
    "SaveAISearchHistoryRequest",
    "SaveAISearchHistoryResponse",
    "AISearchHistoryItem",
    "AISearchHistoryListResponse",
    "PopularPromptItem",
    "PopularPromptsResponse",
]


