"""
Background Itinerary Module Seeding & Maintenance Worker.
Decomposes LLM itineraries into reusable arrival/core/departure modules and
periodically refreshes destination inventory to prevent data staleness.
"""

from datetime import datetime, timezone
import json
from typing import Any, Optional

from ..db.itinerary_module_dao import ItineraryModuleDAO
from .slot_mapper import SlotMapper


class ItineraryModuleWorker:
    """
    Background worker that decomposes LLM-generated itineraries into modular building blocks
    and manages background refresh jobs.
    """

    def __init__(self, dao: Optional[ItineraryModuleDAO] = None, config: Optional[Any] = None):
        self.config = config
        self.dao = dao or ItineraryModuleDAO(config=config)

    @staticmethod
    def decompose_itinerary_to_modules(
        days_list: list[dict[str, Any]],
        destination: str,
        duration_days: int,
        trip_type: str = "flight",
        style: str = "balanced",
        arrival_slot: str = "12_14",
        departure_slot: str = "16_18",
        is_test: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Decomposes a list of day objects into modular building blocks:
        - Day 1 -> module_type='arrival', day_index=0, time_slot=arrival_slot, style=style
        - Day 2..N-1 -> module_type='core_day', day_index=1..N-2, time_slot=None, style=style
        - Day N -> module_type='departure', day_index=-1, time_slot=departure_slot, style=style
        """
        dest_clean = str(destination).strip().lower()
        tt_clean = str(trip_type).strip().lower()
        style_clean = str(style).strip().lower()
        modules = []

        total_days = len(days_list)
        if total_days == 0:
            return modules

        for idx, day in enumerate(days_list, start=1):
            if idx == 1:
                # Arrival Day
                modules.append({
                    "destination": dest_clean,
                    "trip_type": tt_clean,
                    "style": style_clean,
                    "duration_days": duration_days,
                    "module_type": "arrival",
                    "time_slot": arrival_slot,
                    "day_index": 0,
                    "content": day,
                    "is_test": is_test,
                })
            elif idx == total_days and total_days > 1:
                # Departure Day
                modules.append({
                    "destination": dest_clean,
                    "trip_type": tt_clean,
                    "style": style_clean,
                    "duration_days": duration_days,
                    "module_type": "departure",
                    "time_slot": departure_slot,
                    "day_index": -1,
                    "content": day,
                    "is_test": is_test,
                })
            else:
                # Core Day
                core_idx = idx - 1
                modules.append({
                    "destination": dest_clean,
                    "trip_type": tt_clean,
                    "style": style_clean,
                    "duration_days": duration_days,
                    "module_type": "core_day",
                    "time_slot": None,
                    "day_index": core_idx,
                    "content": day,
                    "is_test": is_test,
                })

        return modules

    def seed_generated_itinerary(
        self,
        days_list: list[dict[str, Any]],
        destination: str,
        duration_days: int,
        trip_type: str = "flight",
        style: str = "balanced",
        arrival_slot: str = "12_14",
        departure_slot: str = "16_18",
        created_by: str = "planner_llm",
        is_test: bool = False,
    ) -> int:
        """Decomposes and persists generated itinerary days as reusable modules in PostgreSQL."""
        modules = self.decompose_itinerary_to_modules(
            days_list=days_list,
            destination=destination,
            duration_days=duration_days,
            trip_type=trip_type,
            style=style,
            arrival_slot=arrival_slot,
            departure_slot=departure_slot,
            is_test=is_test,
        )
        return self.dao.save_modules_batch(modules, created_by=created_by, is_test=is_test)

    def refresh_destination_modules(
        self,
        destination: str,
        duration_days: int = 4,
        trip_type: str = "flight",
        arrival_slots: Optional[list[str]] = None,
        departure_slots: Optional[list[str]] = None,
        planner_service: Optional[Any] = None,
        is_test: bool = False,
    ) -> dict[str, Any]:
        """
        Background maintenance job: Re-synthesizes/refreshes modules for a destination using LLM.
        """
        dest_clean = str(destination).strip().lower()
        slots_arr = arrival_slots or SlotMapper.get_standard_2hr_slots()
        slots_dep = departure_slots or SlotMapper.get_standard_2hr_slots()

        results = {"destination": dest_clean, "trip_type": trip_type, "refreshed_slots": [], "modules_saved": 0}

        if planner_service:
            try:
                for a_slot in slots_arr:
                    for d_slot in slots_dep:
                        res = planner_service.generate_itinerary(
                            prompt=f"Comprehensive {duration_days} day travel itinerary for {dest_clean}",
                            origin="ATL",
                            destination=dest_clean,
                            days=duration_days,
                            include_flights=(trip_type == "flight"),
                            include_cars=True,
                            force_refresh=True,
                            is_test=is_test,
                        )
                        days = res.get("itinerary") or res.get("daily_itinerary") or []
                        if days:
                            count = self.seed_generated_itinerary(
                                days_list=days,
                                destination=dest_clean,
                                duration_days=duration_days,
                                trip_type=trip_type,
                                arrival_slot=a_slot,
                                departure_slot=d_slot,
                                created_by="background_worker",
                                is_test=is_test,
                            )
                            results["modules_saved"] += count
                            results["refreshed_slots"].append(f"{a_slot}_{d_slot}")
            except Exception as err:
                results["error"] = str(err)

        return results

    def refresh_all_stale_modules(
        self,
        max_age_days: int = 14,
        planner_service: Optional[Any] = None,
    ) -> dict[str, Any]:
        """
        Periodic weekly/monthly background maintenance job:
        Scans all distinct destinations and triggers background refresh.
        """
        destinations = self.dao.get_distinct_destinations()
        refreshed = []
        for dest in destinations:
            for tt in ["flight", "road_trip"]:
                res = self.refresh_destination_modules(
                    destination=dest,
                    duration_days=4,
                    trip_type=tt,
                    planner_service=planner_service,
                )
                refreshed.append(res)

        return {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "destinations_checked": len(destinations),
            "results": refreshed,
        }
