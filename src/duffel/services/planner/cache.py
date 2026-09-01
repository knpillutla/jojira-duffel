from typing import Any, Optional
from ..slot_mapper import SlotMapper
from ...db.itinerary_module_dao import ItineraryModuleDAO
from ..itinerary_assembly import ItineraryAssemblyEngine
from ..itinerary_worker import ItineraryModuleWorker

# High-Performance Tier-0 In-Memory Process Cache (<0.1ms latency)
_L1_PLANNER_MEMORY_CACHE: dict[str, dict[str, Any]] = {}
_MAX_L1_CACHE_ITEMS = 500


def get_memory_cached_plan(cache_key: str) -> Optional[dict[str, Any]]:
    """Gets cached plan from Tier-0 in-memory dict."""
    return _L1_PLANNER_MEMORY_CACHE.get(cache_key)


def set_memory_cached_plan(cache_key: str, data: dict[str, Any]):
    """Stores plan in Tier-0 in-memory dict with capacity constraint."""
    if len(_L1_PLANNER_MEMORY_CACHE) >= _MAX_L1_CACHE_ITEMS:
        _L1_PLANNER_MEMORY_CACHE.clear()
    _L1_PLANNER_MEMORY_CACHE[cache_key] = data


def lookup_modular_cache_and_modules(
    cache_svc: Any,
    config: Any,
    dest_clean: str,
    origin_code: str,
    start_date: str,
    duration_days: int,
    is_road_trip: bool,
    effective_style: str,
    budget: str,
    passengers_count: int,
    rooms_calculated: int,
    cars_calculated: int,
    include_flights: bool,
    include_hotels: bool,
    include_cars: bool,
    interests: Optional[list[str]],
    outbound_dep: str,
    outbound_arr: str,
    return_dep: str,
    return_arr: str,
    component_pricing: dict[str, Any],
    base_lat: float,
    base_lng: float,
    is_test_mode: bool,
    force_refresh: bool,
) -> tuple[Optional[list[dict[str, Any]]], Optional[dict[str, Any]], str, str]:
    """
    Checks L1 Redis fast cache for compiled itinerary and L2 PostgreSQL for stored modules.
    Returns (days_list, llm_meta, source_type, modular_redis_key).
    """
    effective_trip_type = "road_trip" if is_road_trip else "flight"
    arrival_slot = SlotMapper.map_time_to_slot(outbound_arr, default_slot="12_14")
    departure_slot = SlotMapper.map_time_to_slot(return_dep, default_slot="16_18")
    pref_hash = SlotMapper.generate_preference_hash(
        style=effective_style,
        budget=budget,
        passengers_count=passengers_count,
        include_flights=include_flights,
        include_hotels=include_hotels,
        include_cars=include_cars,
        interests=interests,
    )
    modular_redis_key = SlotMapper.build_redis_cache_key(
        destination=dest_clean,
        duration_days=duration_days,
        trip_type=effective_trip_type,
        arrival_slot=arrival_slot,
        departure_slot=departure_slot,
        pref_hash=pref_hash,
    )

    # 1. Check L1 Redis
    if cache_svc and cache_svc.enabled and not force_refresh:
        cached_modular = cache_svc.get(modular_redis_key)
        if cached_modular and isinstance(cached_modular, dict):
            print(f"[+] L1 MODULAR REDIS CACHE HIT (<1ms) for key: {modular_redis_key}")
            return None, cached_modular, "modular_redis_cache", modular_redis_key

    # 2. Check L2 PostgreSQL
    if not force_refresh:
        try:
            module_dao = ItineraryModuleDAO(config=config)
            stored_modules = module_dao.get_modules(
                destination=dest_clean,
                duration_days=duration_days,
                trip_type=effective_trip_type,
                style=effective_style,
                arrival_slot=arrival_slot,
                departure_slot=departure_slot,
                is_test=is_test_mode,
            )
            if stored_modules and len(stored_modules) >= min(duration_days, 2):
                print(f"[+] L2 MODULAR POSTGRESQL MODULES HIT (<5ms) for '{dest_clean}' ({len(stored_modules)} modules). Assembling statelessly.")
                days_out = ItineraryAssemblyEngine.assemble_itinerary_from_modules(
                    modules=stored_modules,
                    destination=dest_clean,
                    origin=origin_code,
                    start_date=start_date,
                    duration_days=duration_days,
                    trip_type=effective_trip_type,
                    passengers_count=passengers_count,
                    include_flights=include_flights,
                    include_hotels=include_hotels,
                    include_cars=include_cars,
                    base_lat=base_lat,
                    base_lng=base_lng,
                    outbound_dep=outbound_dep,
                    outbound_arr=outbound_arr,
                    return_dep=return_dep,
                    return_arr=return_arr,
                    flight_cost=component_pricing.get("flight_cost", 0.0),
                    hotel_cost_per_night=component_pricing.get("hotel_cost_per_night", 0.0),
                    car_cost_total=component_pricing.get("car_cost_total", 0.0),
                    is_hotel_tbd=bool(component_pricing.get("is_hotel_tbd", False)),
                    is_car_tbd=bool(component_pricing.get("is_car_tbd", False)),
                    rooms_calculated=rooms_calculated,
                    cars_calculated=cars_calculated,
                    is_road_trip=is_road_trip,
                )
                meta = {
                    "is_live_llm": False,
                    "llm_provider": "modular_assembly_engine",
                    "llm_model": "postgres_jsonb_modules",
                }
                return days_out, meta, "modular_postgres_assembly", modular_redis_key
        except Exception as mod_err:
            print(f"[PLANNER MODULE NOTICE] PostgreSQL module lookup notice: {mod_err}")

    return None, None, "live_llm", modular_redis_key


def seed_itinerary_to_postgres(
    config: Any,
    days_list: list[dict[str, Any]],
    destination: str,
    duration_days: int,
    trip_type: str,
    style: str,
    arrival_slot: str,
    departure_slot: str,
    is_test_mode: bool,
):
    """Auto-seeds generated itinerary modules to PostgreSQL for future sub-5ms retrieval."""
    try:
        module_dao = ItineraryModuleDAO(config=config)
        worker = ItineraryModuleWorker(dao=module_dao, config=config)
        seeded_count = worker.seed_generated_itinerary(
            days_list=days_list,
            destination=destination,
            duration_days=duration_days,
            trip_type=trip_type,
            style=style,
            arrival_slot=arrival_slot,
            departure_slot=departure_slot,
            created_by="planner_engine",
            is_test=is_test_mode,
        )
        print(f"[PLANNER SEEDING] Auto-seeded {seeded_count} modules into PostgreSQL for '{destination}'.")
    except Exception as seed_err:
        print(f"[PLANNER SEEDING NOTICE] Auto-seeding notice: {seed_err}")
