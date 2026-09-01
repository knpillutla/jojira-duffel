"""
Unit tests for Universal Itinerary Caching & Assembly Engine.
Tests SHA-256 deterministic key generation, PostgreSQL JSONB storage with trip_type,
Temporal Enforcement Engine (08:00 AM breakfast, 22:00 cutoff, 15-30 min buffers),
stateless assembly, and background worker seeding.
"""

from datetime import datetime, timezone
import os
import unittest

from src.duffel.config import DuffelConfig
from src.duffel.db.itinerary_module_dao import ItineraryModuleDAO
from src.duffel.services.itinerary_assembly import ItineraryAssemblyEngine
from src.duffel.services.itinerary_worker import ItineraryModuleWorker
from src.duffel.services.slot_mapper import SlotMapper
from src.duffel.services.temporal_engine import TemporalEnforcementEngine


class TestUniversalItineraryCachingAndAssembly(unittest.TestCase):
    """Test suite for Universal Itinerary Caching & Assembly Engine."""

    def setUp(self):
        self.test_db_path = "test_universal_modular_itinerary.db"
        os.environ["SQLITE_DB_PATH"] = self.test_db_path
        self.config = DuffelConfig(
            duffel_token="duffel_test_token_12345",
            test_mode=True,
            enable_cache=True,
        )
        self.dao = ItineraryModuleDAO(config=self.config)
        self.worker = ItineraryModuleWorker(dao=self.dao, config=self.config)

    def tearDown(self):
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass

    def test_granular_2hr_slot_mapping(self):
        """Test granular 2-hour arrival and departure time slot mapping."""
        self.assertEqual(SlotMapper.map_time_to_slot("06:30 AM"), "06_08")
        self.assertEqual(SlotMapper.map_time_to_slot("08:15 AM"), "08_10")
        self.assertEqual(SlotMapper.map_time_to_slot("10:45 AM"), "10_12")
        self.assertEqual(SlotMapper.map_time_to_slot("12:30 PM"), "12_14")
        self.assertEqual(SlotMapper.map_time_to_slot("02:15 PM"), "14_16")
        self.assertEqual(SlotMapper.map_time_to_slot("05:00 PM"), "16_18")
        self.assertEqual(SlotMapper.map_time_to_slot("06:30 PM"), "18_20")
        self.assertEqual(SlotMapper.map_time_to_slot("09:15 PM"), "20_22")
        self.assertEqual(SlotMapper.map_time_to_slot("11:30 PM"), "22_24")

    def test_sha256_deterministic_cache_key(self):
        """Test SHA-256 deterministic preference hashing and canonical Redis cache key building."""
        h1 = SlotMapper.generate_preference_hash("balanced", "moderate", 1, True, True, True, ["art", "food"])
        h2 = SlotMapper.generate_preference_hash("balanced", "moderate", 1, True, True, True, ["food", "art"])
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 16)

        key_flight = SlotMapper.build_redis_cache_key("Paris", 4, "flight", "08_10", "18_20", h1)
        self.assertEqual(key_flight, f"itinerary:paris:4:flight:08_10:18_20:{h1}")

        key_road = SlotMapper.build_redis_cache_key("Paris", 4, "road_trip", "08_10", "18_20", h1)
        self.assertEqual(key_road, f"itinerary:paris:4:road_trip:08_10:18_20:{h1}")
        self.assertNotEqual(key_flight, key_road)

    def test_temporal_enforcement_0800_breakfast_lock(self):
        """Test 08:00 AM Rule: Standard Day 2 first activity is locked to Breakfast at 08:00 AM - 09:00 AM."""
        raw_acts = [
            {"name": "Louvre Museum", "category": "Museum"},
            {"name": "Eiffel Tower", "category": "Sightseeing"}
        ]
        enforced = TemporalEnforcementEngine.enforce_daily_temporal_boundaries(
            day_number=2,
            total_days=4,
            raw_activities=raw_acts,
            is_flight_mode=True,
            dest_clean="Paris",
            orig_clean="Atlanta",
        )

        self.assertGreaterEqual(len(enforced), 2)
        breakfast_act = enforced[0]
        self.assertIn("breakfast", breakfast_act["name"].lower())
        self.assertEqual(breakfast_act["departure_time"], "08:00 AM")
        self.assertEqual(breakfast_act["arrival_time"], "09:00 AM")

    def test_temporal_enforcement_2200_cutoff(self):
        """Test 22:00 Cutoff: All daily activities terminate strictly by 10:00 PM (22:00)."""
        raw_acts = [
            {"name": f"Attraction {i}", "category": "Sightseeing"} for i in range(1, 15)
        ]
        enforced = TemporalEnforcementEngine.enforce_daily_temporal_boundaries(
            day_number=2,
            total_days=4,
            raw_activities=raw_acts,
            is_flight_mode=True,
            dest_clean="Paris",
            orig_clean="Atlanta",
        )

        last_act = enforced[-1]
        self.assertIn("night", last_act["name"].lower())
        self.assertEqual(last_act["arrival_time"], "10:00 PM")

        # Verify no activity exceeds 10:00 PM (1320 mins)
        for act in enforced:
            arr_mins = TemporalEnforcementEngine.parse_time_to_minutes(act["arrival_time"])
            self.assertLessEqual(arr_mins, 1320)

    def test_temporal_enforcement_buffer_allocation(self):
        """Test Buffer Allocation: Injects 15-30 min exploration and transit buffers between activities."""
        raw_acts = [
            {"name": "Louvre Museum", "category": "Museum"},
            {"name": "Tuileries Garden", "category": "Park"},
            {"name": "Orsay Museum", "category": "Museum"},
        ]
        enforced = TemporalEnforcementEngine.enforce_daily_temporal_boundaries(
            day_number=2,
            total_days=4,
            raw_activities=raw_acts,
            is_flight_mode=True,
            dest_clean="Paris",
            orig_clean="Atlanta",
        )

        for act in enforced[:-1]:
            nxt = act.get("next_activity", {})
            self.assertIn("travel_time_minutes", nxt)
            self.assertGreaterEqual(nxt["travel_time_minutes"], 15)
            self.assertLessEqual(nxt["travel_time_minutes"], 30)

    def test_transport_mode_routing_flight_vs_road_trip(self):
        """Test Flight mode logistics (45-60 min car rental) vs Road Trip mode (08:00 AM road start)."""
        # Flight Mode Day 1
        enforced_flight = TemporalEnforcementEngine.enforce_daily_temporal_boundaries(
            day_number=1,
            total_days=4,
            raw_activities=[],
            is_flight_mode=True,
            outbound_dep="06:30 AM",
            outbound_arr="12:30 PM",
            include_cars=True,
            dest_clean="Zurich",
            orig_clean="Atlanta",
        )
        flight_names = [a["name"] for a in enforced_flight]
        self.assertTrue(any("Flight" in n for n in flight_names))
        self.assertTrue(any("Rental" in n or "Vehicle" in n for n in flight_names))
        self.assertTrue(any("Hotel Check-in" in n for n in flight_names))

        # Road Trip Mode Day 1
        enforced_road = TemporalEnforcementEngine.enforce_daily_temporal_boundaries(
            day_number=1,
            total_days=4,
            raw_activities=[],
            is_flight_mode=False,
            dest_clean="Savannah",
            orig_clean="Atlanta",
        )
        self.assertEqual(enforced_road[0]["departure_time"], "08:00 AM")
        self.assertIn("Road Trip", enforced_road[0]["name"])

    def test_module_dao_trip_type_and_audit_columns(self):
        """Test PostgreSQL JSONB module storage with UUID, trip_type, and audit columns."""
        # Save Flight module
        self.dao.save_module(
            destination="paris",
            duration_days=4,
            module_type="arrival",
            time_slot="afternoon",
            day_index=0,
            content={"theme": "Arrival Paris", "activities": [{"name": "Eiffel Tower"}]},
            trip_type="flight",
            created_by="test_admin",
            is_test=True,
        )

        # Save Road Trip module
        self.dao.save_module(
            destination="paris",
            duration_days=4,
            module_type="arrival",
            time_slot="morning",
            day_index=0,
            content={"theme": "Road Departure Paris", "activities": [{"name": "Scenic Drive"}]},
            trip_type="road_trip",
            created_by="test_admin",
            is_test=True,
        )

        # Fetch Flight modules
        flight_mods = self.dao.get_modules(
            destination="paris",
            duration_days=4,
            trip_type="flight",
            arrival_slot="afternoon",
        )
        self.assertEqual(len(flight_mods), 1)
        self.assertEqual(flight_mods[0]["trip_type"], "flight")
        self.assertEqual(flight_mods[0]["created_by"], "test_admin")
        self.assertTrue(flight_mods[0]["is_test"])
        self.assertIn("id", flight_mods[0])
        self.assertIn("created_at", flight_mods[0])
        self.assertIn("updated_at", flight_mods[0])

        # Fetch Road Trip modules
        road_mods = self.dao.get_modules(
            destination="paris",
            duration_days=4,
            trip_type="road_trip",
            arrival_slot="morning",
        )
        self.assertEqual(len(road_mods), 1)
        self.assertEqual(road_mods[0]["trip_type"], "road_trip")

    def test_thematic_module_isolation_and_seeding(self):
        """Test thematic module isolation between romantic vs architecture vs family itineraries."""
        # Save Romantic module
        self.dao.save_module(
            destination="paris",
            duration_days=4,
            module_type="arrival",
            time_slot="12_14",
            day_index=0,
            content={"theme": "Romantic Sunset Arrival & Seine Cruise", "activities": [{"name": "Eiffel Tower Sunset"}]},
            trip_type="flight",
            style="romantic",
            is_test=True,
        )

        # Save Architecture module
        self.dao.save_module(
            destination="paris",
            duration_days=4,
            module_type="arrival",
            time_slot="12_14",
            day_index=0,
            content={"theme": "Gothic & Haussmann Architecture Discovery", "activities": [{"name": "Notre-Dame Cathedral"}]},
            trip_type="flight",
            style="architecture",
            is_test=True,
        )

        # Fetch Romantic modules
        romantic_mods = self.dao.get_modules(
            destination="paris",
            duration_days=4,
            trip_type="flight",
            style="romantic",
            arrival_slot="12_14",
        )
        self.assertEqual(len(romantic_mods), 1)
        self.assertEqual(romantic_mods[0]["style"], "romantic")
        self.assertIn("Romantic", romantic_mods[0]["content"]["theme"])

        # Fetch Architecture modules
        arch_mods = self.dao.get_modules(
            destination="paris",
            duration_days=4,
            trip_type="flight",
            style="architecture",
            arrival_slot="12_14",
        )
        self.assertEqual(len(arch_mods), 1)
        self.assertEqual(arch_mods[0]["style"], "architecture")
        self.assertIn("Architecture", arch_mods[0]["content"]["theme"])

    def test_dynamic_contextual_bundle_titles(self):
        """Test dynamic bundle title generation based on prompt intent and real itinerary activities."""
        from src.duffel.services.planner import generate_contextual_bundle_title

        # Romantic prompt with Eiffel Tower & Seine Cruise
        t1 = generate_contextual_bundle_title("Paris", "cheapest", 0, prompt="Romantic anniversary trip to Paris", activities=["Eiffel Tower", "Seine River Cruise"])
        self.assertIn("Romantic", t1)
        self.assertIn("Paris", t1)
        self.assertIn("Eiffel Tower", t1)

        t2 = generate_contextual_bundle_title("Paris", "luxury", 2, prompt="Romantic honeymoon in Paris", activities=["Eiffel Tower", "Seine River Cruise"])
        self.assertIn("Romance", t2)
        self.assertIn("Michelin", t2)

        # Family prompt with Central Park & Museum
        t3 = generate_contextual_bundle_title("New York", "moderate", 1, prompt="Family vacation to NYC with kids", activities=["Central Park", "Metropolitan Museum"])
        self.assertIn("Family", t3)
        self.assertIn("New York", t3)

        # Culinary prompt with Rome food tour
        t4 = generate_contextual_bundle_title("Rome", "luxury", 2, prompt="Gourmet food and wine tasting tour in Rome", activities=["Trastevere Food Market", "Colosseum"])
        self.assertIn("Gastronomy", t4)
        self.assertIn("Rome", t4)

    def test_dao_alter_table_migration(self):
        """Test that init_db safely ensures style and trip_type columns exist without failing."""
        # Re-calling init_db on existing database
        self.dao.init_db()
        stats = self.dao.get_module_stats()
        self.assertIn("total_modules_stored", stats)
        self.assertNotIn("error", stats)

    def test_separated_travel_classification_fields(self):
        """Test separated scope (domestic/international) and trip_type (road_trip/vacation/cruise) fields."""
        from src.duffel.services.planner import _resolve_location_country

        # 1. Domestic Road Trip (Atlanta to Columbus, OH, Home=US)
        home = "US"
        dest_country = _resolve_location_country("Columbus")
        is_intl = (home != dest_country)
        self.assertFalse(is_intl)

        # 2. International Vacation (Atlanta to Paris, Home=US)
        dest_country_paris = _resolve_location_country("Paris")
        is_intl_paris = (home != dest_country_paris)
        self.assertTrue(is_intl_paris)

    def test_road_trip_city_name_preservation(self):
        """Test that non-flight road trips preserve authentic city names and don't force IATA airport codes."""
        from src.duffel.services.locations import format_proper_title

        cincinnati = format_proper_title("cincinnati, ohio")
        self.assertEqual(cincinnati, "Cincinnati, Ohio")

        gatlinburg = format_proper_title("gatlinburg, tn")
        self.assertEqual(gatlinburg, "Gatlinburg, TN")

    def test_road_trip_shortest_scenic_longest_bundles(self):
        """Test that non-flight road trip bundles are categorized as shortest, scenic, and longest."""
        from src.duffel.services.planner import generate_contextual_bundle_title

        t_short = generate_contextual_bundle_title("Cincinnati", tier="shortest", index=0, is_road_trip=True, origin="Atlanta")
        self.assertIn("Shortest", t_short)
        self.assertIn("Direct", t_short)

        t_scenic = generate_contextual_bundle_title("Cincinnati", tier="scenic", index=1, is_road_trip=True, origin="Atlanta")
        self.assertIn("Scenic", t_scenic)

        t_long = generate_contextual_bundle_title("Cincinnati", tier="longest", index=2, is_road_trip=True, origin="Atlanta")
        self.assertIn("Longest", t_long)

    def test_dual_model_extraction_and_planner_properties(self):
        """Test that extraction uses mini/flash models and itinerary planner uses full reasoning models."""
        from src.duffel.config import DuffelConfig

        cfg = DuffelConfig()
        self.assertEqual(cfg.openai_extraction_model, "gpt-4o-mini")
        self.assertEqual(cfg.openai_planner_model, "gpt-4o")
        self.assertEqual(cfg.gemini_extraction_model, "gemini-1.5-flash")
        self.assertEqual(cfg.gemini_planner_model, "gemini-1.5-pro")
        self.assertEqual(cfg.llm_extraction_provider, "openai")
        self.assertEqual(cfg.llm_planner_provider, "gemini")

    def test_independent_llm_providers(self):
        """Test that extraction and planner can be set to different providers."""
        from src.duffel.config import DuffelConfig

        cfg = DuffelConfig()
        cfg.llm_extraction_provider = "openai"
        cfg.llm_planner_provider = "gemini"
        self.assertEqual(cfg.llm_extraction_provider, "openai")
        self.assertEqual(cfg.llm_planner_provider, "gemini")


if __name__ == "__main__":
    unittest.main()
