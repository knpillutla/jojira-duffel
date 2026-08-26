"""
Prompts Service managing popular and trending search prompts across Flights, Cars, Hotels,
Travel Package Bundles, AI Trip Planner, and AI Search.
"""

from typing import Any, Optional
from .base import BaseService


class PromptsService(BaseService):
    """
    Service for retrieving and tracking trending travel search prompts and search parameters.
    Supports filtering by category (flights, cars, hotels, bundles, ai_trip_planner, ai_search).
    Provides structured search_params so UI can populate search panel form fields when a prompt is clicked.
    """

    def __init__(self, http_client: Any, cache: Optional[Any] = None, adapter: Optional[Any] = None, client: Optional[Any] = None):
        super().__init__(http_client, cache=cache, adapter=adapter)
        self.client_app = client

    def get_popular_prompts(
        self,
        category: Optional[str] = None,
        limit: int = 6,
    ) -> dict[str, Any]:
        """
        Retrieves popular / trending prompts grouped by category or filtered by a specific category.
        """
        all_templates = self._get_curated_prompts()
        cat_clean = category.lower().strip() if category else None

        if cat_clean and cat_clean not in ("all", "*"):
            filtered_templates = {cat_clean: all_templates.get(cat_clean, [])}
        else:
            filtered_templates = all_templates

        result_categories: dict[str, list[dict[str, Any]]] = {}
        total_count = 0

        for cat_name, items in filtered_templates.items():
            limited_items = items[:limit]
            result_categories[cat_name] = limited_items
            total_count += len(limited_items)

        return {
            "status": "success",
            "categories": result_categories,
            "total_prompts": total_count,
        }

    def _get_curated_prompts(self) -> dict[str, list[dict[str, Any]]]:
        """Curated high-converting trending prompts with structured form population parameters."""
        return {
            "flights": [
                {
                    "id": "p_fl_001",
                    "title": "✈️ Nonstop ATL to Paris CDG",
                    "prompt": "Nonstop flights from ATL to Paris CDG in October for 7 days",
                    "category": "flights",
                    "badge": "🔥 Top Trending",
                    "trending_score": 98,
                    "search_params": {
                        "origin": "ATL",
                        "destination": "CDG",
                        "departure_date": "2026-10-01",
                        "return_date": "2026-10-08",
                        "passengers_count": 1,
                        "cabin_class": "economy",
                        "trip_type": "round_trip"
                    }
                },
                {
                    "id": "p_fl_002",
                    "title": "🇬🇧 JFK to London LHR Round-Trip",
                    "prompt": "Cheapest round-trip flights from JFK to London LHR for 7 days",
                    "category": "flights",
                    "badge": "💰 Best Value",
                    "trending_score": 95,
                    "search_params": {
                        "origin": "JFK",
                        "destination": "LHR",
                        "departure_date": "2026-10-01",
                        "return_date": "2026-10-08",
                        "passengers_count": 1,
                        "cabin_class": "economy",
                        "trip_type": "round_trip"
                    }
                },
                {
                    "id": "p_fl_003",
                    "title": "🥂 Business Class to Tokyo HND",
                    "prompt": "Business class flight from LAX to Tokyo HND",
                    "category": "flights",
                    "badge": "✨ Premium",
                    "trending_score": 92,
                    "search_params": {
                        "origin": "LAX",
                        "destination": "HND",
                        "departure_date": "2026-11-01",
                        "return_date": "2026-11-10",
                        "passengers_count": 1,
                        "cabin_class": "business",
                        "trip_type": "round_trip"
                    }
                },
                {
                    "id": "p_fl_004",
                    "title": "🌴 Miami MIA Weekend Getaway",
                    "prompt": "Flights from ORD to Miami MIA for weekend trip",
                    "category": "flights",
                    "badge": "☀️ Weekend",
                    "trending_score": 89,
                    "search_params": {
                        "origin": "ORD",
                        "destination": "MIA",
                        "departure_date": "2026-10-15",
                        "return_date": "2026-10-18",
                        "passengers_count": 2,
                        "cabin_class": "economy",
                        "trip_type": "round_trip"
                    }
                }
            ],
            "cars": [
                {
                    "id": "p_cr_001",
                    "title": "🚗 SUV Rental in London LHR",
                    "prompt": "SUV car rental at London LHR for 7 days",
                    "category": "cars",
                    "badge": "🔥 Top Car Choice",
                    "trending_score": 96,
                    "search_params": {
                        "pickup_location": "LHR",
                        "dropoff_location": "LHR",
                        "pickup_datetime": "2026-10-01T10:00:00Z",
                        "dropoff_datetime": "2026-10-08T10:00:00Z",
                        "driver_age": 30,
                        "vehicle_category": "SUV"
                    }
                },
                {
                    "id": "p_cr_002",
                    "title": "⚡ Tesla Model Y in Paris CDG",
                    "prompt": "Tesla Model Y electric car rental in Paris CDG for 5 days",
                    "category": "cars",
                    "badge": "⚡ Electric SUV",
                    "trending_score": 93,
                    "search_params": {
                        "pickup_location": "CDG",
                        "dropoff_location": "CDG",
                        "pickup_datetime": "2026-10-01T10:00:00Z",
                        "dropoff_datetime": "2026-10-06T10:00:00Z",
                        "driver_age": 30,
                        "vehicle_category": "Electric"
                    }
                },
                {
                    "id": "p_cr_003",
                    "title": "🏖️ Convertible Rental in Miami MIA",
                    "prompt": "Convertible rental car at Miami MIA for weekend",
                    "category": "cars",
                    "badge": "🌴 Popular",
                    "trending_score": 90,
                    "search_params": {
                        "pickup_location": "MIA",
                        "dropoff_location": "MIA",
                        "pickup_datetime": "2026-10-15T10:00:00Z",
                        "dropoff_datetime": "2026-10-18T10:00:00Z",
                        "driver_age": 25,
                        "vehicle_category": "Convertible"
                    }
                }
            ],
            "hotels": [
                {
                    "id": "p_ht_001",
                    "title": "🏨 5-Star Luxury Hotel in Paris",
                    "prompt": "5-star luxury hotel in central Paris for 7 nights",
                    "category": "hotels",
                    "badge": "⭐ 5-Star Luxury",
                    "trending_score": 97,
                    "search_params": {
                        "location": "Paris",
                        "check_in_date": "2026-10-01",
                        "check_out_date": "2026-10-08",
                        "rooms": 1,
                        "guests_count": 2
                    }
                },
                {
                    "id": "p_ht_002",
                    "title": "🇬🇧 Boutique Hotel in London",
                    "prompt": "Boutique hotel stay in central London for 4 nights",
                    "category": "hotels",
                    "badge": "✨ Top Rated",
                    "trending_score": 94,
                    "search_params": {
                        "location": "London",
                        "check_in_date": "2026-10-01",
                        "check_out_date": "2026-10-05",
                        "rooms": 1,
                        "guests_count": 1
                    }
                },
                {
                    "id": "p_ht_003",
                    "title": "🌊 Beachfront Resort in Miami",
                    "prompt": "Beachfront resort stay in Miami for 2 guests",
                    "category": "hotels",
                    "badge": "🏖️ Ocean View",
                    "trending_score": 91,
                    "search_params": {
                        "location": "Miami",
                        "check_in_date": "2026-10-15",
                        "check_out_date": "2026-10-18",
                        "rooms": 1,
                        "guests_count": 2
                    }
                }
            ],
            "bundles": [
                {
                    "id": "p_bn_001",
                    "title": "📦 Flight + Hotel Package to Paris",
                    "prompt": "Flight from ATL to CDG with 5-star hotel in Paris and 5% package discount",
                    "category": "bundles",
                    "badge": "🏷️ 5% Package Savings",
                    "trending_score": 99,
                    "search_params": {
                        "origin": "ATL",
                        "destination": "CDG",
                        "departure_date": "2026-10-01",
                        "return_date": "2026-10-08",
                        "passengers_count": 1,
                        "cabin_class": "economy",
                        "rooms": 1,
                        "driver_age": 30,
                        "selected_types": ["flights", "hotels"]
                    }
                },
                {
                    "id": "p_bn_002",
                    "title": "🚘 Flight + Hotel + Car Package to London",
                    "prompt": "Flight + Hotel + Car rental package to London LHR for 7 days",
                    "category": "bundles",
                    "badge": "🔥 Complete Package",
                    "trending_score": 96,
                    "search_params": {
                        "origin": "JFK",
                        "destination": "LHR",
                        "departure_date": "2026-10-01",
                        "return_date": "2026-10-08",
                        "passengers_count": 2,
                        "cabin_class": "economy",
                        "rooms": 1,
                        "driver_age": 30,
                        "selected_types": ["flights", "hotels", "cars"]
                    }
                },
                {
                    "id": "p_bn_003",
                    "title": "🎌 Business Class + Luxury Hotel Bundle Tokyo",
                    "prompt": "Luxury Flight + 5-star Hotel bundle to Tokyo HND",
                    "category": "bundles",
                    "badge": "👑 Signature Luxury",
                    "trending_score": 93,
                    "search_params": {
                        "origin": "LAX",
                        "destination": "HND",
                        "departure_date": "2026-11-01",
                        "return_date": "2026-11-10",
                        "passengers_count": 1,
                        "cabin_class": "business",
                        "rooms": 1,
                        "driver_age": 30,
                        "selected_types": ["flights", "hotels"]
                    }
                }
            ],
            "ai_trip_planner": [
                {
                    "id": "p_tp_001",
                    "title": "🗺️ 5-Day Cultural Itinerary in Paris",
                    "prompt": "5-day cultural & food itinerary in Paris with map landmark coordinates",
                    "category": "ai_trip_planner",
                    "badge": "📍 Map Coordinates",
                    "trending_score": 98,
                    "search_params": {
                        "destination": "Paris",
                        "origin": "ATL",
                        "start_date": "2026-10-01",
                        "end_date": "2026-10-06",
                        "passengers_count": 1,
                        "interests": ["culture", "sightseeing", "food"]
                    }
                },
                {
                    "id": "p_tp_002",
                    "title": "🏛️ 7-Day Historic London Itinerary",
                    "prompt": "7-day London sightseeing itinerary with top landmarks and daily activities",
                    "category": "ai_trip_planner",
                    "badge": "👑 Top Tour",
                    "trending_score": 95,
                    "search_params": {
                        "destination": "London",
                        "origin": "JFK",
                        "start_date": "2026-10-01",
                        "end_date": "2026-10-08",
                        "passengers_count": 2,
                        "interests": ["history", "museums", "landmarks"]
                    }
                },
                {
                    "id": "p_tp_003",
                    "title": "🍜 4-Day Tokyo Tech & Food Itinerary",
                    "prompt": "4-day Tokyo itinerary covering tech, ramen, and iconic sights",
                    "category": "ai_trip_planner",
                    "badge": "⭐ Highly Rated",
                    "trending_score": 92,
                    "search_params": {
                        "destination": "Tokyo",
                        "origin": "LAX",
                        "start_date": "2026-11-01",
                        "end_date": "2026-11-05",
                        "passengers_count": 1,
                        "interests": ["food", "tech", "shopping"]
                    }
                }
            ],
            "ai_search": [
                {
                    "id": "p_as_001",
                    "title": "🤖 AI Flight + Hotel + Attractions in Paris",
                    "prompt": "Flight from ATL to CDG, 4-star hotel in Paris, and top attractions to visit",
                    "category": "ai_search",
                    "badge": "🧠 Natural AI Search",
                    "trending_score": 99,
                    "search_params": {
                        "origin": "ATL",
                        "destination": "CDG",
                        "departure_date": "2026-10-01",
                        "return_date": "2026-10-08",
                        "passengers_count": 1,
                        "selected_types": ["flights", "hotels", "attractions"]
                    }
                },
                {
                    "id": "p_as_002",
                    "title": "🤖 AI Weekend in London with Car",
                    "prompt": "Weekend trip to London with flight, hotel, and rental car",
                    "category": "ai_search",
                    "badge": "🔥 AI Multi-Domain",
                    "trending_score": 95,
                    "search_params": {
                        "origin": "JFK",
                        "destination": "LHR",
                        "departure_date": "2026-10-01",
                        "return_date": "2026-10-04",
                        "passengers_count": 2,
                        "selected_types": ["flights", "hotels", "cars"]
                    }
                },
                {
                    "id": "p_as_003",
                    "title": "🤖 AI Attractions & Resort Stay in Miami",
                    "prompt": "Top attractions in Miami and 3-night hotel resort stay",
                    "category": "ai_search",
                    "badge": "🌴 Resort & Tour",
                    "trending_score": 91,
                    "search_params": {
                        "destination": "Miami",
                        "departure_date": "2026-10-15",
                        "return_date": "2026-10-18",
                        "passengers_count": 2,
                        "selected_types": ["hotels", "attractions"]
                    }
                }
            ]
        }
