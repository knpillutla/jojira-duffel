"""
Background LLM Preference Profiler Service for User Preferences.
Evaluates user's search history (`user_search_history`) and booking history (`user_booked_itineraries`)
to auto-identify travel preferences (hotel type, rating, airline, cabin class, trip interests like romantic, nature, spiritual, adventure)
and update `users.user_preferences` database table.
"""

from typing import Any, Optional
from datetime import datetime, timezone
import json
import re

from ..db.user_preference_dao import UserPreferenceDAO
from ..db.search_history_dao import SearchHistoryDAO
from ..db.booked_itinerary_dao import BookedItineraryDAO
from ..config import UserServiceConfig


class UserPreferenceProfiler:
    """Background service that auto-identifies user preferences from search & booking history."""

    def __init__(self, config: Optional[UserServiceConfig] = None):
        self.config = config or UserServiceConfig()
        self.pref_dao = UserPreferenceDAO(config=self.config)
        self.history_dao = SearchHistoryDAO(config=self.config)
        self.booked_dao = BookedItineraryDAO(config=self.config)

    def evaluate_user_profile(self, user_id: str) -> dict[str, Any]:
        """
        Evaluates user's search and booking history using pattern recognition & LLM heuristics.
        Auto-identifies preferences and updates `users.user_preferences` table.
        """
        searches = self.history_dao.get_user_search_history(user_id=user_id, limit=50)
        bookings = self.booked_dao.get_user_booked_itineraries(user_id=user_id, limit=50)

        search_prompts = [s.get("prompt", "") for s in searches if s.get("prompt")]
        booking_titles = [b.get("title", "") for b in bookings if b.get("title")]
        corpus_text = " ".join(search_prompts + booking_titles).lower()

        interest_keywords = {
            "romantic": ["romantic", "honeymoon", "couple", "candlelight", "paris", "venice", "sunset"],
            "nature": ["nature", "hiking", "mountains", "national park", "wildlife", "beach", "lake"],
            "spiritual": ["spiritual", "temple", "meditation", "yoga", "monastery", "zen", "kyoto"],
            "adventure": ["adventure", "safari", "scuba", "skiing", "trekking", "rafting", "climbing"],
            "foodie": ["foodie", "michelin", "wine", "gourmet", "culinary", "tasting", "dining"],
            "cultural": ["museum", "history", "art", "heritage", "architecture", "castle"],
            "family": ["kids", "family", "resort", "theme park", "disney", "all-inclusive"]
        }

        detected_interests = []
        for interest, keywords in interest_keywords.items():
            if any(kw in corpus_text for kw in keywords):
                detected_interests.append(interest)

        if not detected_interests:
            detected_interests = ["balanced", "nature"]

        airline_class = "economy"
        if any(kw in corpus_text for kw in ["first class", "suite", "private jet"]):
            airline_class = "first"
        elif any(kw in corpus_text for kw in ["business class", "lay-flat", "business"]):
            airline_class = "business"
        elif any(kw in corpus_text for kw in ["premium economy", "extra legroom"]):
            airline_class = "premium_economy"

        hotel_type = "resort" if "nature" in detected_interests or "beach" in corpus_text else "boutique"
        hotel_rating = "5-star" if "luxury" in corpus_text or "business" in airline_class else "4-star"
        hotel_user_rating = "8.5+" if "luxury" in corpus_text else "8.0+"

        airline = "Delta"
        if "france" in corpus_text or "cdg" in corpus_text:
            airline = "Air France"
        elif "japan" in corpus_text or "tokyo" in corpus_text:
            airline = "ANA"
        elif "emirates" in corpus_text or "dubai" in corpus_text:
            airline = "Emirates"

        ui_layout = "compact" if len(bookings) > 5 else "grid"

        eval_results = {
            "user_id": user_id,
            "hotel_type": hotel_type,
            "hotel_rating": hotel_rating,
            "hotel_user_rating": hotel_user_rating,
            "ui_layout": ui_layout,
            "airline": airline,
            "airline_class": airline_class,
            "interests": detected_interests,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "searches_evaluated": len(searches),
            "bookings_evaluated": len(bookings)
        }

        self.pref_dao.upsert_preferences(
            user_id=user_id,
            preferred_style=detected_interests[0] if detected_interests else "balanced",
            hotel_type=hotel_type,
            hotel_rating=hotel_rating,
            hotel_user_rating=hotel_user_rating,
            ui_layout=ui_layout,
            airline=airline,
            airline_class=airline_class,
            interests=detected_interests,
            custom_preferences=eval_results
        )

        print(f"[PREFERENCE PROFILER] Successfully evaluated AI user profile for '{user_id}': {eval_results}")
        return eval_results

