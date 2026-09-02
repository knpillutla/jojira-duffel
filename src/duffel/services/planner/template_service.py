"""
Itinerary Template Service: Decouples date-agnostic activity schedule generation
and PostgreSQL persistence from live AI Natural Search pricing.
Strict file limit under 200 lines adhering to repository modular standards.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ...db.itinerary_module_dao import ItineraryModuleDAO
from ..itinerary_worker import ItineraryModuleWorker
from .llm import orchestrate_llm_itinerary
from .prompts import build_planner_system_prompt
from ...prompts.builder import build_planner_user_prompt


def get_or_create_itinerary_template(
    config: Any,
    dest_clean: str,
    origin_code: str,
    duration_days: int,
    trip_type: str,
    style: str,
    budget: str,
    passengers_count: int,
    prompt: str,
    base_lat: float,
    base_lng: float,
    include_attractions: bool = True,
    include_activities: bool = True,
    include_cars: bool = True,
    is_road_trip: bool = False,
    is_cruise: bool = False,
    is_test_mode: bool = False,
    force_refresh: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """
    Checks PostgreSQL for date-agnostic activity modules for (destination, duration_days, style).
    If found: Returns stored modules immediately (<5ms, 0 LLM tokens).
    If missing: Invokes LLM once to generate date-agnostic activities, saves to PostgreSQL,
    and returns the freshly seeded modules.
    """
    module_dao = ItineraryModuleDAO(config=config)
    eff_trip_type = "road_trip" if is_road_trip else ("cruise" if is_cruise else "flight")
    eff_style = style or "balanced"

    # 1. Check PostgreSQL Database First
    if not force_refresh:
        try:
            stored_modules = module_dao.get_modules(
                destination=dest_clean,
                duration_days=duration_days,
                trip_type=eff_trip_type,
                style=eff_style,
                is_test=is_test_mode,
            )
            if stored_modules and len(stored_modules) >= min(duration_days, 2):
                c_key = f"{dest_clean.lower()}-{duration_days}day-{eff_style.lower()}-itinerary"
                print(f"[CACHE HIT: POSTGRESQL] Retrieved pre-generated itinerary template '{c_key}' (<3ms).")
                meta = {
                    "is_live_llm": False,
                    "llm_provider": "postgresql_template",
                    "llm_model": "itinerary_modules",
                    "template_key": c_key,
                }
                return stored_modules, meta, "modular_postgres_template"
        except Exception as db_err:
            print(f"[ITINERARY TEMPLATE NOTICE] PostgreSQL lookup notice: {db_err}")

    # 2. On Cache Miss: Generate date-agnostic activity schedule via LLM
    c_key = f"{dest_clean.lower()}-{duration_days}day-{eff_style.lower()}-itinerary"
    print(f"[CACHE MISS] Template '{c_key}' not found in database. Generating via LLM and seeding to PostgreSQL...")

    sys_prompt = build_planner_system_prompt(config)
    dummy_start = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
    dummy_end = (datetime.now() + timedelta(days=15 + duration_days)).strftime("%Y-%m-%d")

    user_prompt, resolved_style = build_planner_user_prompt(
        prompt=prompt, origin_code=origin_code, dest_clean=dest_clean,
        start_date=dummy_start, end_date=dummy_end, duration_days=duration_days,
        passengers_count=passengers_count, rooms_calculated=1, cars_calculated=1,
        style=eff_style, budget=budget or "moderate", include_flights=not is_road_trip,
        include_hotels=True, include_cars=include_cars, include_trains=False,
        include_buses=False, include_attractions=include_attractions,
        include_activities=include_activities, include_seasonal_attractions=True,
        include_seasonal_activities=True, is_road_trip=is_road_trip, is_cruise=is_cruise,
        is_fly_and_drive=False, outbound_dep="08:00 AM", outbound_arr="12:00 PM",
        return_dep="05:00 PM", return_arr="09:00 PM",
    )

    llm_days, llm_meta = orchestrate_llm_itinerary(
        config=config, system_prompt=sys_prompt, user_prompt=user_prompt,
        destination=dest_clean, duration_days=duration_days,
        start_dt=datetime.strptime(dummy_start, "%Y-%m-%d"),
        base_lat=base_lat, base_lng=base_lng,
        include_attractions=include_attractions,
        include_activities=include_activities,
        include_cars=include_cars, origin=origin_code,
        is_road_trip=is_road_trip,
    )

    # 3. Save / Seed generated days into PostgreSQL with standard audit columns
    if llm_days:
        try:
            worker = ItineraryModuleWorker(dao=module_dao, config=config)
            seeded_count = worker.seed_generated_itinerary(
                days_list=llm_days,
                destination=dest_clean,
                duration_days=duration_days,
                trip_type=eff_trip_type,
                style=resolved_style or eff_style,
                arrival_slot="12_14",
                departure_slot="16_18",
                created_by="planner_engine",
                is_test=is_test_mode,
            )
            print(f"[ITINERARY TEMPLATE PERSISTENCE] Persisted {seeded_count} modules under key '{c_key}'.")
        except Exception as seed_err:
            print(f"[ITINERARY TEMPLATE WARN] Failed seeding template to database: {seed_err}")

        # Retrieve or decompose into module objects for dynamic assembly
        modules = ItineraryModuleWorker.decompose_itinerary_to_modules(
            days_list=llm_days,
            destination=dest_clean,
            duration_days=duration_days,
            trip_type=eff_trip_type,
            style=resolved_style or eff_style,
            is_test=is_test_mode,
        )
        return modules, llm_meta or {}, "llm_generated_and_seeded"

    return [], llm_meta or {}, "empty_template"
