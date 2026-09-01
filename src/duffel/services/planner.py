"""
Travel Planner Service Module Bridge.
Delegates all functionality to the decoupled, single-responsibility modules in src.duffel.services.planner.
Strictly complies with the 200-300 lines limit rule.
"""
from .planner import (
    DESTINATION_GEO_MAP,
    TravelPlannerService,
    format_proper_title,
    classify_travel_scope_and_type,
    generate_contextual_bundle_title,
    build_top_3_bundles,
    build_planner_system_prompt,
    build_planner_user_prompt,
    generate_activity_reviews,
    _generate_activity_reviews,
    enrich_activity_urls_and_geo,
    calculate_haversine_distance,
    _calculate_haversine_distance,
    parse_time_to_minutes,
    format_minutes_to_time,
    extract_days_from_llm_payload,
    _extract_days_from_llm_payload,
    _resolve_location_country,
    orchestrate_llm_itinerary,
    _LLM_METRICS_COUNTER,
    lookup_modular_cache_and_modules,
    seed_itinerary_to_postgres,
)

__all__ = [
    "DESTINATION_GEO_MAP",
    "TravelPlannerService",
    "format_proper_title",
    "classify_travel_scope_and_type",
    "generate_contextual_bundle_title",
    "build_top_3_bundles",
    "build_planner_system_prompt",
    "build_planner_user_prompt",
    "generate_activity_reviews",
    "_generate_activity_reviews",
    "enrich_activity_urls_and_geo",
    "calculate_haversine_distance",
    "_calculate_haversine_distance",
    "parse_time_to_minutes",
    "format_minutes_to_time",
    "extract_days_from_llm_payload",
    "_extract_days_from_llm_payload",
    "_resolve_location_country",
    "orchestrate_llm_itinerary",
    "_LLM_METRICS_COUNTER",
    "lookup_modular_cache_and_modules",
    "seed_itinerary_to_postgres",
]
