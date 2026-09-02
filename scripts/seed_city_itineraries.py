"""
Standalone Seeding Script: Pre-generates 1-7 Day City Itineraries upfront.
Stores modular activity timelines into PostgreSQL / SQLite database (and JSON files),
enabling instantaneous date and live pricing interpolation at runtime.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Optional

# Add project root to sys.path to ensure module imports work reliably
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.duffel.config import DuffelConfig
from src.duffel.db.itinerary_module_dao import ItineraryModuleDAO
from src.duffel.services.itinerary_worker import ItineraryModuleWorker
from src.duffel.services.locations import GEO_LOCATIONS, format_proper_title
from src.duffel.prompts import build_planner_system_prompt, build_planner_user_prompt
from src.duffel.services.planner.llm import orchestrate_llm_itinerary


DEFAULT_POPULAR_CITIES = [
    "Paris",
    "London",
    "Rome",
    "Tokyo",
    "Barcelona",
    "New York",
    "Dubai",
    "Amsterdam",
    "Zurich",
    "Orlando",
]


def parse_arguments() -> argparse.Namespace:
    """Parses CLI arguments for the one-time itinerary seeding script."""
    parser = argparse.ArgumentParser(
        description="Pre-generate and seed 1 to 7-day city itineraries upfront for instant pricing interpolation."
    )
    parser.add_argument(
        "--cities",
        type=str,
        default=",".join(DEFAULT_POPULAR_CITIES),
        help="Comma-separated list of popular destination cities.",
    )
    parser.add_argument(
        "--min-days",
        type=int,
        default=1,
        help="Minimum itinerary duration in days (default: 1).",
    )
    parser.add_argument(
        "--max-days",
        type=int,
        default=7,
        help="Maximum itinerary duration in days (default: 7).",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-generate and overwrite existing itinerary modules even if already seeded.",
    )
    parser.add_argument(
        "--export-dir",
        type=str,
        default=str(PROJECT_ROOT / "output" / "seeded_itineraries"),
        help="Directory to export JSON backup files of seeded itineraries.",
    )
    return parser.parse_args()


def get_city_coordinates(city: str) -> tuple[float, float]:
    """Resolves latitude and longitude for the target city, or returns sensible center."""
    city_upper = city.strip().upper()
    geo = GEO_LOCATIONS.get(city_upper) or GEO_LOCATIONS.get(city.strip().lower(), {})
    lat = float(geo.get("latitude", 48.8566))
    lng = float(geo.get("longitude", 2.3522))
    return lat, lng


def seed_single_itinerary(
    config: DuffelConfig,
    dao: ItineraryModuleDAO,
    worker: ItineraryModuleWorker,
    city: str,
    duration_days: int,
    force_refresh: bool = False,
    export_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Generates a comprehensive itinerary via LLM and stores it for both flight and road trip modalities."""
    dest_clean = format_proper_title(city)
    style = "balanced"
    trip_types = ["flight", "road_trip"]

    # 1. Check if modules already exist unless force_refresh is requested
    if not force_refresh:
        existing_flight = dao.get_modules(
            destination=dest_clean,
            duration_days=duration_days,
            trip_type="flight",
            style=style,
        )
        if existing_flight and len(existing_flight) >= min(duration_days, 2):
            print(f"[-] Skipped: {dest_clean} ({duration_days} days) already exists in DB.")
            return {"status": "skipped", "city": dest_clean, "duration_days": duration_days}

    print(f"[*] Generating {duration_days}-day itinerary for '{dest_clean}'...")
    now = datetime.now(timezone.utc)
    start_dt = now + timedelta(days=30)
    start_date_str = start_dt.strftime("%Y-%m-%d")
    end_date_str = (start_dt + timedelta(days=duration_days - 1)).strftime("%Y-%m-%d")
    base_lat, base_lng = get_city_coordinates(dest_clean)

    # 2. Build system & user prompts
    system_prompt = build_planner_system_prompt(config)
    user_prompt, effective_style = build_planner_user_prompt(
        prompt=f"Comprehensive {duration_days}-day travel itinerary for {dest_clean}",
        origin_code="JFK",
        dest_clean=dest_clean,
        start_date=start_date_str,
        end_date=end_date_str,
        duration_days=duration_days,
        passengers_count=1,
        rooms_calculated=1,
        cars_calculated=1,
        style=style,
        budget="moderate",
        include_flights=True,
        include_hotels=True,
        include_cars=True,
        include_trains=False,
        include_buses=False,
        include_attractions=True,
        include_activities=True,
        include_seasonal_attractions=True,
        include_seasonal_activities=True,
        is_road_trip=False,
        is_cruise=False,
        is_fly_and_drive=False,
        outbound_dep="08:00 AM",
        outbound_arr="12:00 PM",
        return_dep="05:00 PM",
        return_arr="10:00 PM",
    )

    # 3. Call LLM to orchestrate itinerary
    llm_days, llm_meta = orchestrate_llm_itinerary(
        config=config,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        destination=dest_clean,
        duration_days=duration_days,
        start_dt=start_dt,
        base_lat=base_lat,
        base_lng=base_lng,
        include_attractions=True,
        include_activities=True,
        include_cars=True,
        origin="JFK",
        is_road_trip=False,
    )

    if not llm_days:
        raise RuntimeError(f"Failed to generate itinerary for {dest_clean} ({duration_days} days): Empty LLM output.")

    # 4. Seed into Database for both modalities so future queries hit L2 cache statelessly
    saved_modules = 0
    for tt in trip_types:
        saved_count = worker.seed_generated_itinerary(
            days_list=llm_days,
            destination=dest_clean,
            duration_days=duration_days,
            trip_type=tt,
            style=effective_style,
            arrival_slot="12_14",
            departure_slot="16_18",
            created_by="seed_script",
            is_test=False,
        )
        saved_modules += saved_count

    # 5. Export JSON backup
    if export_dir:
        export_dir.mkdir(parents=True, exist_ok=True)
        slug = dest_clean.lower().replace(" ", "_")
        json_file = export_dir / f"{slug}_{duration_days}_days.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump({
                "city": dest_clean,
                "duration_days": duration_days,
                "generated_at": now.isoformat(),
                "llm_metadata": llm_meta,
                "days": llm_days,
            }, f, indent=2, ensure_ascii=False)

    print(f"[+] Successfully seeded {dest_clean} ({duration_days} days) - {saved_modules} modules saved across modalities.")
    return {"status": "seeded", "city": dest_clean, "duration_days": duration_days, "modules": saved_modules}


def main():
    """Main entry point for batch itinerary pre-seeding."""
    args = parse_arguments()
    config = DuffelConfig()
    dao = ItineraryModuleDAO(config=config)
    worker = ItineraryModuleWorker(dao=dao, config=config)
    export_dir = Path(args.export_dir)

    cities = [c.strip() for c in args.cities.split(",") if c.strip()]
    durations = list(range(args.min_days, args.max_days + 1))

    total_tasks = len(cities) * len(durations)
    print("=" * 70)
    print(f"Pre-generating Upfront Itineraries for {len(cities)} Cities (Days {args.min_days} to {args.max_days})")
    print(f"Total target combinations: {total_tasks}")
    print(f"Storage: {dao.db_engine.upper()} | Export directory: {export_dir}")
    print("=" * 70)

    summary = {"seeded": 0, "skipped": 0, "errors": 0}
    for city in cities:
        for days in durations:
            try:
                res = seed_single_itinerary(
                    config=config,
                    dao=dao,
                    worker=worker,
                    city=city,
                    duration_days=days,
                    force_refresh=args.force_refresh,
                    export_dir=export_dir,
                )
                status = res.get("status", "seeded")
                summary[status] = summary.get(status, 0) + 1
            except Exception as err:
                summary["errors"] += 1
                print(f"[!] Error seeding {city} ({days} days): {err}")

    print("\n" + "=" * 70)
    print(f"Summary: Seeded: {summary['seeded']} | Skipped: {summary['skipped']} | Errors: {summary['errors']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
