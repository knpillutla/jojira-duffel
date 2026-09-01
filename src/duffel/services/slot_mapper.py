"""
Slot Mapping Middleware & Canonical Cache Key Generator.
Converts raw flight/travel timestamps into categorical slots (morning, afternoon, evening)
and computes deterministic preference hashes for high cache hit rates.
"""

from datetime import datetime
import hashlib
import re
from typing import Any, Optional


class SlotMapper:
    """
    Slot mapping middleware that deterministically categorizes arrival and departure times
    into standardized morning, afternoon, and evening buckets.
    """

    @staticmethod
    def parse_time_to_minutes(time_val: Any, default_val: int = 720) -> int:
        """Parses any time string, dict, or ISO timestamp into minutes from midnight (0..1439)."""
        if not time_val:
            return default_val

        if isinstance(time_val, dict):
            ts = str(
                time_val.get("departure_time")
                or time_val.get("arrival_time")
                or time_val.get("time_slot")
                or time_val.get("time")
                or time_val.get("departing_at")
                or time_val.get("arriving_at")
                or ""
            ).upper().strip()
        else:
            ts = str(time_val).upper().strip()

        # Check ISO timestamp format (e.g. 2026-09-16T12:30:00Z)
        if "T" in ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return dt.hour * 60 + dt.minute
            except Exception:
                pass

        # Check standard 12-hour format e.g. 12:30 PM, 06:30 AM
        match = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)", ts)
        if match:
            h = int(match.group(1))
            m = int(match.group(2))
            ampm = match.group(3)
            if ampm == "PM" and h != 12:
                h += 12
            elif ampm == "AM" and h == 12:
                h = 0
            return h * 60 + m

        # Check 24-hour format e.g. 14:30
        match24 = re.search(r"\b(\d{1,2}):(\d{2})\b", ts)
        if match24:
            h = int(match24.group(1))
            m = int(match24.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h * 60 + m

        if "BREAKFAST" in ts or "MORNING" in ts:
            return 480  # 08:00 AM
        if "LUNCH" in ts or "NOON" in ts:
            return 720  # 12:00 PM
        if "AFTERNOON" in ts:
            return 840  # 02:00 PM
        if "EVENING" in ts:
            return 1065 # 05:45 PM
        if "DINNER" in ts or "NIGHT" in ts:
            return 1200 # 08:00 PM

        return default_val

    @classmethod
    def map_time_to_slot(cls, time_val: Any, default_slot: str = "12_14") -> str:
        """
        Maps a timestamp to a granular 2-hour time slot bucket:
        - '06_08': 06:00 AM - 07:59 AM (360 - 479 mins)
        - '08_10': 08:00 AM - 09:59 AM (480 - 599 mins)
        - '10_12': 10:00 AM - 11:59 AM (600 - 719 mins)
        - '12_14': 12:00 PM - 01:59 PM (720 - 839 mins)
        - '14_16': 02:00 PM - 03:59 PM (840 - 959 mins)
        - '16_18': 04:00 PM - 05:59 PM (960 - 1079 mins)
        - '18_20': 06:00 PM - 07:59 PM (1080 - 1199 mins)
        - '20_22': 08:00 PM - 09:59 PM (1200 - 1319 mins)
        - '22_24': 10:00 PM - 11:59 PM (1320 - 1439 mins)
        """
        if not time_val:
            return default_slot

        # Normalize legacy word slots if explicitly passed
        ts_upper = str(time_val).upper().strip()
        if ts_upper == "MORNING":
            return "08_10"
        elif ts_upper == "AFTERNOON":
            return "12_14"
        elif ts_upper == "EVENING":
            return "18_20"
        elif ts_upper == "NIGHT":
            return "20_22"

        mins = cls.parse_time_to_minutes(time_val, default_val=750)
        start_h = (mins // 120) * 2
        start_h = max(0, min(22, start_h))
        end_h = start_h + 2
        return f"{start_h:02d}_{end_h:02d}"

    @classmethod
    def get_standard_2hr_slots(cls) -> list[str]:
        """Returns the list of standard 2-hour travel operational slots."""
        return [
            "06_08", "08_10", "10_12", "12_14", "14_16", "16_18", "18_20", "20_22"
        ]

    @staticmethod
    def generate_preference_hash(
        style: str = "balanced",
        budget: str = "moderate",
        passengers_count: int = 1,
        include_flights: bool = True,
        include_hotels: bool = True,
        include_cars: bool = True,
        interests: Optional[list[str]] = None,
    ) -> str:
        """
        Computes an immutable SHA-256 deterministic hash representing traveler preferences & selected components.
        Enables ultra-fast cache reuse across travelers sharing similar profiles while maintaining cache segmentation.
        """
        interests_sorted = sorted([str(i).strip().lower() for i in (interests or [])])
        components_str = f"fl:{int(include_flights)}_ht:{int(include_hotels)}_car:{int(include_cars)}"
        raw_sig = f"{style.strip().lower()}|{budget.strip().lower()}|pax:{passengers_count}|{components_str}|{','.join(interests_sorted)}"
        return hashlib.sha256(raw_sig.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def build_redis_cache_key(
        cls,
        destination: str,
        duration_days: int,
        trip_type: str = "flight",
        arrival_slot: str = "afternoon",
        departure_slot: str = "afternoon",
        pref_hash: str = "default",
    ) -> str:
        """
        Builds the deterministic SHA-256 canonical Redis cache key pattern:
        itinerary:{destination}:{duration}:{trip_type}:{arrival_slot}:{departure_slot}:{pref_hash}
        """
        dest_clean = str(destination).strip().lower().replace(" ", "-")
        trip_type_clean = str(trip_type).strip().lower().replace(" ", "_")
        arr_clean = str(arrival_slot).strip().lower()
        dep_clean = str(departure_slot).strip().lower()
        return f"itinerary:{dest_clean}:{duration_days}:{trip_type_clean}:{arr_clean}:{dep_clean}:{pref_hash}"
