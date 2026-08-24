"""
Interactive Terminal Menu UI for Duffel REST API integration.
"""

import json
import os
import sys
from typing import Any, Optional

from ..client import DuffelClient
from ..config import DuffelConfig
from ..models.common import Passenger, Payment
from .interactive import fill_car_slots, fill_optimized_flight_slots, fill_standard_flight_slots, fill_stay_slots, prompt_input
from .parser import PromptExtractor


class DuffelCLI:
    """Terminal Menu interface for searching and booking flights, stays, and cars."""

    def __init__(self):
        token = os.environ.get("DUFFEL_API_TOKEN", "")
        self.client = DuffelClient(api_token=token, debug=False)

    def run(self):
        """Start the interactive CLI main loop."""
        self._print_header()
        while True:
            self._print_menu()
            choice = input("\n>> Enter menu option (0-11): ").strip()
            if choice == "1":
                self._handle_standard_flights_menu()
            elif choice == "2":
                self._handle_optimized_flights_menu()
            elif choice == "3":
                self._handle_natural_language_flights_menu()
            elif choice == "4":
                self._handle_book_flight_menu()
            elif choice == "5":
                self._handle_stays()
            elif choice == "6":
                self._handle_book_stay_menu()
            elif choice == "7":
                self._handle_cars()
            elif choice == "8":
                self._handle_book_car_menu()
            elif choice == "9":
                self._handle_config()
            elif choice == "10":
                self._handle_clear_redis_cache()
            elif choice == "11":
                self._handle_launch_api_server()
            elif choice in ("0", "q", "exit", "quit"):
                print("\nThank you for using Jajira LLC Duffel API Client. Goodbye!\n")
                break
            else:
                print("[!] Invalid selection. Please choose an option from 0 to 11.")

    def _print_header(self):
        print("=" * 65)
        print("     JAJIRA LLC - DUFFEL API INTEGRATION CLIENT (REST)   ")
        print("=" * 65)

    def _print_menu(self):
        token_status = f"API Token Set ({self.client.config.api_token[:10]}...)" if self.client.config.api_token else "[!] API Token Not Set"
        print("\n" + "-" * 55)
        print(f"Status: {token_status}")
        print("-" * 55)
        print(" --- FLIGHTS ---")
        print(" [1] Standard Flight Search (Exact Departure & Return Dates)")
        print(" [2] Optimized Price Search (Find Cheapest Dates by Duration)")
        print(" [3] Natural Language Flight Search (AI Prompt Resolution)")
        print(" [4] Book Flight Offer")
        print("\n --- STAYS (HOTELS) ---")
        print(" [5] Search Stays (Hotels)")
        print(" [6] Book Stay Offer")
        print("\n --- CARS (CAR RENTALS) ---")
        print(" [7] Search Cars (Car Rentals)")
        print(" [8] Book Car Offer")
        print("\n --- CONFIGURATION & CACHE ---")
        print(" [9] Configure Duffel API Key")
        print(" [10] Clear / Flush Redis Cache Database")
        print("\n --- REST API WEB SERVER ---")
        print(" [11] Launch REST API Web Server (FastAPI / Uvicorn)")
        print(" [0] Exit")
        print("-" * 55)

    def _handle_launch_api_server(self):
        print("\n--- [REST API] Launch Web Server (FastAPI) ---")
        print("Starting FastAPI Uvicorn web server at http://127.0.0.1:8000...")
        import uvicorn
        print("OpenAPI Interactive Docs: http://127.0.0.1:8000/docs")
        uvicorn.run("src.duffel.api.app:app", host="127.0.0.1", port=8000, reload=True)

    def _handle_clear_redis_cache(self):
        print("\n--- [REDIS CACHE] Clear / Flush Database ---")
        confirm = prompt_input("Are you sure you want to flush ALL cached entries in Redis? (y/n)", default="n", required=False).lower()
        if confirm in ("y", "yes"):
            self.client.cache.clear()
            print("\n[+] Redis cache database successfully cleared!")
        else:
            print("\nOperation cancelled. Cache intact.")

    def _handle_standard_flights_menu(self):
        print("\n--- [FLIGHTS] Standard Exact-Date Flight Search ---")
        prompt = input("\nDescribe your flight request in natural language (e.g. 'JFK to LHR on Sept 22 returning Sept 29') or press Enter:\n> ").strip()
        extracted = PromptExtractor.extract_flight_info(prompt) if prompt else {}
        extracted["search_prompt"] = prompt
        self._handle_standard_flights(extracted)

    def _handle_standard_flights(self, extracted: dict):
        slots = fill_standard_flight_slots(extracted)
        passengers = [Passenger(type="adult") for _ in range(slots['passengers_count'])]

        print(f"\n⏳ Executing exact-date flight search for {slots['origin']} -> {slots['destination']} on {slots['departure_date']}...")
        try:
            offers = self.client.flights.search_exact(
                origin=slots['origin'],
                destination=slots['destination'],
                departure_date=slots['departure_date'],
                return_date=slots['return_date'],
                passengers=passengers,
                cabin_class=slots['cabin_class'],
                progress_callback=print
            )
            if hasattr(offers, "__dict__"):
                setattr(offers, "search_prompt", extracted.get("search_prompt", ""))
                setattr(offers, "search_params", dict(slots))

            self._display_and_book_offers(offers)
        except Exception as err:
            print(f"\n[!] Error during Standard Exact-Date Flight search: {err}")

    def _handle_natural_language_flights_menu(self):
        print("\n--- [FLIGHTS] Natural Language AI Flight Search ---")
        prompt = input("\nEnter your natural language flight request (e.g. 'Fly from JFK to LHR for 7 days in October'):\n> ").strip()
        if not prompt:
            print("Operation cancelled. Prompt cannot be empty.")
            return

        print(f"\n🧠 Resolving natural-language prompt with Gemini AI: '{prompt}'...")
        extracted = PromptExtractor.extract_flight_info(prompt)
        extracted["search_prompt"] = prompt

        missing_fields = PromptExtractor.missing_flight_fields(extracted)
        if missing_fields:
            print("\n[!] Missing required flight information: " + ", ".join(missing_fields))
            print("    Please provide a prompt with origin, destination, and departure date or travel month.")
            return

        fav_airline = extracted.get("favorite_airline", "")
        print(f"\n[+] AI Successfully Parsed Flight Details:")
        slices = extracted.get("slices", [{}])
        s1 = slices[0] if slices else {}
        print(f"  * Origin         : {s1.get('origin', 'N/A')}")
        print(f"  * Destination    : {s1.get('destination', 'N/A')}")
        print(f"  * Target Date    : {s1.get('departure_date', 'N/A')}")
        if len(slices) > 1:
            print(f"  * Return Date    : {slices[1].get('departure_date', 'N/A')}")
        if extracted.get("duration_days"):
            print(f"  * Duration       : {extracted['duration_days']} days")
        if fav_airline:
            print(f"  * Preferred      : {fav_airline}")

        confirm = prompt_input("\nExecute search with these extracted parameters? (Y/n)", default="y", required=False).lower()
        if confirm not in ("y", "yes"):
            print("Operation cancelled.")
            return

        self._handle_optimized_flights(extracted)

    def _handle_optimized_flights_menu(self):
        print("\n--- [FLIGHTS] Optimized Price Search (Cheapest Dates by Duration) ---")
        prompt = input("\nDescribe your flight request in natural language (e.g. 'JFK to LHR for 7 days') or press Enter:\n> ").strip()
        extracted = PromptExtractor.extract_flight_info(prompt) if prompt else {}
        extracted["search_prompt"] = prompt
        if prompt:
            missing_fields = PromptExtractor.missing_flight_fields(extracted)
            if missing_fields:
                print("\n[!] Missing required flight information: " + ", ".join(missing_fields))
                return
        self._handle_optimized_flights(extracted)

    def _handle_optimized_flights(self, extracted: dict):
        slots = fill_optimized_flight_slots(extracted)
        passengers = [Passenger(type="adult") for _ in range(slots['passengers_count'])]

        # Analyze candidate queries to check Redis cache status vs Duffel API calls
        analysis = self.client.flights.analyze_candidate_queries(
            origin=slots['origin'],
            destination=slots['destination'],
            target_date=slots['target_date'],
            target_return_date=slots['target_return_date'],
            min_duration_days=slots['min_duration_days'],
            max_duration_days=slots['max_duration_days'],
            flex_days=slots['flex_days'],
            passengers=passengers,
            cabin_class=slots['cabin_class'],
        )

        total_batches = analysis['total_batches']
        duffel_calls = analysis['duffel_api_calls']
        redis_hits = analysis['redis_cache_hits']
        is_tier1 = analysis.get("is_tier1_hit", False)

        print("\n=================================================================")
        if is_tier1:
            print("[+] OPTIMIZED FLIGHT SEARCH CONFIGURATION (TIER-1 AGGREGATED CACHE HIT)")
        else:
            print("[+] OPTIMIZED FLIGHT SEARCH CONFIGURATION")
        print("=================================================================")
        print(f"  * Route                   : {slots['origin']} -> {slots['destination']}")
        print(f"  * Target Departure Date   : {slots['target_date']}")
        print(f"  * Target Return Date      : {slots['target_return_date']}")
        print(f"  * Allowed Trip Duration   : {slots['min_duration_days']} to {slots['max_duration_days']} days")
        print(f"  * Cabin Class             : {slots['cabin_class']}")
        print(f"  * Passengers              : {slots['passengers_count']}")
        print("  ---------------------------------------------------------------")
        print(f"  [+] TOTAL CANDIDATE BATCHES        : {total_batches} Batches")
        print(f"  [+] ESTIMATED DUFFEL API CALLS     : {duffel_calls} Calls")
        print(f"  [+] ESTIMATED REDIS CACHE READS    : {redis_hits} Read(s) (0ms latency)")
        print(f"      |-- Tier-1 Aggregated Hits   : {analysis.get('aggregated_cache_hits', 0)}")
        print(f"      +-- Tier-2 Individual Hits   : {analysis.get('individual_cache_hits', 0)}")
        print("  ---------------------------------------------------------------")
        for idx, (d_dep, d_ret, dur, is_cached, status) in enumerate(analysis['details'], 1):
            print(f"    Batch {idx:2d}: Outbound {d_dep} | Return {d_ret} ({dur}-day trip) -> [{status}]")
        print("=================================================================")

        confirm = prompt_input(
            f"\nProceed with executing search ({duffel_calls} Duffel API calls, {redis_hits} Redis hits)? (y/n)",
            default="y",
            required=False
        ).lower()

        if confirm not in ("y", "yes"):
            print("Cancelled search.")
            return

        print(f"\n⏳ Executing {total_batches} price optimization queries ({duffel_calls} Duffel API calls, {redis_hits} Redis hits)...\n")
        try:
            offers = self.client.flights.search_optimized(
                origin=slots['origin'],
                destination=slots['destination'],
                target_date=slots['target_date'],
                target_return_date=slots['target_return_date'],
                min_duration_days=slots['min_duration_days'],
                max_duration_days=slots['max_duration_days'],
                flex_days=slots['flex_days'],
                passengers=passengers,
                cabin_class=slots['cabin_class'],
                progress_callback=print
            )
            if hasattr(offers, "__dict__"):
                setattr(offers, "search_prompt", extracted.get("search_prompt", ""))
                setattr(offers, "search_params", dict(slots))

            self._display_and_book_offers(offers)
        except Exception as err:
            print(f"\n[!] Error during Optimized Flight search: {err}")

    def _display_and_book_offers(self, offers):
        if isinstance(offers, list) and offers:
            # Always sort lowest to highest price
            offers.sort(key=lambda o: float(getattr(o, "total_amount", 0.0) or 0.0))
            best_deal = offers[0]
            best_amt = getattr(best_deal, "total_amount", "0.00")
            best_curr = getattr(best_deal, "total_currency", "USD")
            best_owner = "Airline"
            if hasattr(best_deal, "owner") and isinstance(best_deal.owner, dict):
                best_owner = best_deal.owner.get("name") or best_deal.owner.get("iata_code") or "Airline"

            default_fav_airline = self.client.flights._determine_default_favorite_airline(offers)

            fav_airline_input = prompt_input(
                f"\nEnter Favorite Airline (e.g. 'Frontier', 'Delta', 'BA', 'VS')", default=default_fav_airline, required=False
            )

            self._display_comprehensive_category_highlights(offers, fav_airline=fav_airline_input)
            self._export_search_results_json(offers, fav_airline=fav_airline_input)

            best_offer_id = getattr(best_deal, "id", "")

            best_dur_min = self._get_offer_total_duration_min(best_deal)
            best_dur_str = self._format_duration(best_dur_min)

            print("\n" + "=" * 85)
            print("[+] CHEAPEST OVERALL FLIGHT DEAL DETAILS:")
            print(f"  * Lowest Price        : {best_curr} {best_amt} (Airline: {best_owner})")
            print(f"  * Total Flight Duration: {best_dur_str}")
            print(f"  * Offer ID            : {best_offer_id}")

            best_slices = getattr(best_deal, "slices", [])
            for leg_i, slc in enumerate(best_slices, 1):
                info = self._extract_slice_details(slc)
                carrier_str = f" ({info['carrier']} {info['flight_number']})".strip() if info['carrier'] or info['flight_number'] else ""
                print(f"  * Leg {leg_i} Start -> End    : {info['origin']} [{info['departing_at']}]  -->  {info['destination']} [{info['arriving_at']}]{info['duration']} | {info['stops']}{carrier_str}")
            print("=" * 85)

            max_offers = getattr(self.client.config, "max_cached_offers", 40)
            max_non_stop = getattr(self.client.config, "max_non_stop_offers", 10)

            # 1. Display Top Non-Stop Offers section
            non_stop_list = getattr(offers, "non_stop_offers", None)
            if not non_stop_list:
                non_stop_list = [o for o in offers if self._get_offer_max_stops(o) == 0][:max_non_stop]
            else:
                non_stop_list = non_stop_list[:max_non_stop]

            if non_stop_list:
                print("\n" + "=" * 85)
                print(f"[+] CHEAPEST NON-STOP (0-STOP) FLIGHT OFFERS (Showing Top {len(non_stop_list)} Lowest to Highest Price):")
                print("=" * 85)
                for idx, offer in enumerate(non_stop_list, 1):
                    owner_name = self._get_offer_owner_name(offer)
                    total_amt = getattr(offer, "total_amount", "0.00")
                    total_curr = getattr(offer, "total_currency", "USD")
                    offer_id = getattr(offer, "id", "")
                    total_dur_min = self._get_offer_total_duration_min(offer)
                    dur_str = self._format_duration(total_dur_min)

                    print(f"  [{idx}] Price: {total_curr} {total_amt} | Airline: {owner_name} | Duration: {dur_str} | Offer ID: {offer_id}")

                    offer_slices = getattr(offer, "slices", [])
                    for slice_idx, slc in enumerate(offer_slices, 1):
                        info = self._extract_slice_details(slc)
                        flight_str = f" | {info['carrier']} {info['flight_number']}".strip() if info['carrier'] or info['flight_number'] else ""
                        print(f"      Leg {slice_idx}: {info['origin']} [{info['departing_at']}] -> {info['destination']} [{info['arriving_at']}] | {info['stops']}{info['duration']}{flight_str}")
                    print("-" * 85)
            else:
                print("\n" + "=" * 85)
                print("[+] CHEAPEST NON-STOP (0-STOP) FLIGHT OFFERS:")
                print("  [i] No Non-Stop (0-stop) flights found for this route.")
                print("=" * 85)

            # 2. Display All Overall Offers section
            top_offers = offers[:max_offers]
            print(f"\n[+] CHEAPEST OVERALL FLIGHT OFFERS (Showing All {len(top_offers)} Lowest to Highest Price):")
            print("=" * 85)
            for idx, offer in enumerate(top_offers, 1):
                owner_name = self._get_offer_owner_name(offer)
                total_amt = getattr(offer, "total_amount", "0.00")
                total_curr = getattr(offer, "total_currency", "USD")
                offer_id = getattr(offer, "id", "")
                total_dur_min = self._get_offer_total_duration_min(offer)
                dur_str = self._format_duration(total_dur_min)

                print(f"  [{idx}] Price: {total_curr} {total_amt} | Airline: {owner_name} | Duration: {dur_str} | Offer ID: {offer_id}")

                offer_slices = getattr(offer, "slices", [])
                for slice_idx, slc in enumerate(offer_slices, 1):
                    info = self._extract_slice_details(slc)
                    flight_str = f" | {info['carrier']} {info['flight_number']}".strip() if info['carrier'] or info['flight_number'] else ""
                    print(f"      Leg {slice_idx}: {info['origin']} [{info['departing_at']}] -> {info['destination']} [{info['arriving_at']}] | {info['stops']}{info['duration']}{flight_str}")
                print("-" * 85)

            book_choice = prompt_input("\nSelect offer number from list to book (or 0 to skip)", default="0", required=False)
            if book_choice.isdigit() and 1 <= int(book_choice) <= len(top_offers):
                selected = top_offers[int(book_choice) - 1]
                self._book_flight(selected)
        else:
            print("\n[i] No flight offers returned for this query.")

    def _parse_duration_minutes(self, dur_str: str) -> int:
        """Parse ISO-8601 duration string e.g. 'PT12H30M', 'PT7H15M' into total integer minutes."""
        if not dur_str or not isinstance(dur_str, str):
            return 99999
        import re
        hours = 0
        minutes = 0
        h_match = re.search(r"(\d+)H", dur_str)
        if h_match:
            hours = int(h_match.group(1))
        m_match = re.search(r"(\d+)M", dur_str)
        if m_match:
            minutes = int(m_match.group(1))
        return hours * 60 + minutes

    def _format_duration(self, minutes: int) -> str:
        """Format total minutes into human-readable e.g. '12h 30m'."""
        if minutes >= 99999 or minutes <= 0:
            return "N/A"
        h = minutes // 60
        m = minutes % 60
        if h > 0 and m > 0:
            return f"{h}h {m}m"
        elif h > 0:
            return f"{h}h"
        return f"{m}m"

    def _get_offer_max_stops(self, offer: Any) -> int:
        """Get maximum stops across all slices in an offer."""
        slices = getattr(offer, "slices", []) if hasattr(offer, "slices") else (offer.get("slices", []) if isinstance(offer, dict) else [])
        max_stops = 0
        for slc in slices:
            segs = getattr(slc, "segments", []) if hasattr(slc, "segments") else (slc.get("segments", []) if isinstance(slc, dict) else [])
            stops = max(0, len(segs) - 1)
            if stops > max_stops:
                max_stops = stops
        return max_stops

    def _get_offer_total_duration_min(self, offer: Any) -> int:
        """Get total travel duration in minutes across all slices in an offer."""
        slices = getattr(offer, "slices", []) if hasattr(offer, "slices") else (offer.get("slices", []) if isinstance(offer, dict) else [])
        total_min = 0
        for slc in slices:
            dur_str = getattr(slc, "duration", "") if hasattr(slc, "duration") else (slc.get("duration", "") if isinstance(slc, dict) else "")
            parsed = self._parse_duration_minutes(dur_str)
            if parsed < 99999:
                total_min += parsed
        return total_min if total_min > 0 else 99999

    def _get_offer_owner_name(self, offer: Any) -> str:
        """Extract owner/airline name from offer object or dict."""
        if not offer:
            return "Airline"
        owner = getattr(offer, "owner", None) if hasattr(offer, "owner") else (offer.get("owner") if isinstance(offer, dict) else None)
        if not owner:
            return "Airline"
        if isinstance(owner, dict):
            return owner.get("name") or owner.get("iata_code") or "Airline"
        name = getattr(owner, "name", None)
        if name:
            return str(name)
        iata = getattr(owner, "iata_code", None)
        if iata:
            return str(iata)
        return "Airline"

    def _is_fav_airline(self, offer: Any, fav_query: str) -> bool:
        """Check if offer matches favorite airline (by name or IATA code)."""
        if not fav_query:
            return True
        q = fav_query.strip().lower()
        owner_name = self._get_offer_owner_name(offer).lower()
        owner = getattr(offer, "owner", {}) if hasattr(offer, "owner") else (offer.get("owner", {}) if isinstance(offer, dict) else {})
        iata = (owner.get("iata_code") or "").lower() if isinstance(owner, dict) else ""
        return (q in owner_name or q == iata)

    def _display_comprehensive_category_highlights(self, offers: list, fav_airline: str = ""):
        """Display pricing highlights across 7 categories (Cheapest, Non-Stop, 1-Stop, 2-Stop, Shortest, Favorite Airline, Favorite Shortest)."""
        if not offers:
            return

        # 1. Overall Cheapest Deal
        cheapest_all = min(offers, key=lambda o: float(getattr(o, "total_amount", 0.0) or 0.0))

        # 2. Cheapest Non-Stop (0 Stops)
        non_stop_offers = [o for o in offers if self._get_offer_max_stops(o) == 0]
        cheapest_non_stop = min(non_stop_offers, key=lambda o: float(getattr(o, "total_amount", 0.0) or 0.0)) if non_stop_offers else None

    def _display_comprehensive_category_highlights(self, offers: list, fav_airline: str = ""):
        """Display pricing highlights across 7 categories."""
        if not offers:
            return

        all_airline_highlights = getattr(offers, "airline_highlights", None)
        highlights = getattr(offers, "category_highlights", None)
        if not highlights or fav_airline:
            highlights = self.client.flights.compute_category_highlights(
                offers, favorite_airline=fav_airline, all_airline_highlights=all_airline_highlights
            )

        c_cheapest = highlights.get("overall_cheapest")
        c_ns = highlights.get("cheapest_non_stop")
        c_sns = highlights.get("shortest_non_stop")
        c_1s = highlights.get("cheapest_1_stop")
        c_2s = highlights.get("cheapest_2_stop")
        c_sh = highlights.get("shortest_flight")
        fav_cheap_entry = highlights.get("favorite_airline_cheapest", {})
        fav_short_entry = highlights.get("favorite_airline_shortest", {})

        fav_query = fav_cheap_entry.get("favorite_airline", "Favorite Airline")
        c_fav = fav_cheap_entry.get("offer")
        s_fav = fav_short_entry.get("offer")

        print("\n" + "=" * 95)
        print("[+] COMPREHENSIVE FLIGHT CATEGORY HIGHLIGHTS & PRICING BREAKDOWN")
        print("=" * 95)

        # 1. Overall Cheapest
        if c_cheapest:
            dur = c_cheapest.get('duration', 'N/A')
            print(f"  [1] Overall Cheapest Deal        : {c_cheapest['price']:<12} | Airline: {c_cheapest['airline']:<20} | Duration: {dur:<7} | Offer ID: {c_cheapest['offer_id']}")

        # 2. Cheapest Non-Stop
        if c_ns:
            dur = c_ns.get('duration', 'N/A')
            print(f"  [2] Cheapest Non-Stop (0 Stops)  : {c_ns['price']:<12} | Airline: {c_ns['airline']:<20} | Duration: {dur:<7} | Offer ID: {c_ns['offer_id']}")
        else:
            print("  [2] Cheapest Non-Stop (0 Stops)  : N/A (No Non-Stop flights found for this route)")

        # 3. Shortest Non-Stop
        if c_sns:
            dur = c_sns.get('duration', 'N/A')
            print(f"  [3] Shortest Non-Stop Flight     : {c_sns['price']:<12} | Airline: {c_sns['airline']:<20} | Duration: {dur:<7} | Offer ID: {c_sns['offer_id']}")
        else:
            print("  [3] Shortest Non-Stop Flight     : N/A (No Non-Stop flights found for this route)")

        # 4. 1 Stop
        if c_1s:
            dur = c_1s.get('duration', 'N/A')
            print(f"  [4] Cheapest 1-Stop Flight       : {c_1s['price']:<12} | Airline: {c_1s['airline']:<20} | Duration: {dur:<7} | Offer ID: {c_1s['offer_id']}")
        else:
            print("  [4] Cheapest 1-Stop Flight       : N/A (No 1-Stop flights found for this route)")

        # 5. 2 Stops
        if c_2s:
            dur = c_2s.get('duration', 'N/A')
            print(f"  [5] Cheapest 2-Stop Flight       : {c_2s['price']:<12} | Airline: {c_2s['airline']:<20} | Duration: {dur:<7} | Offer ID: {c_2s['offer_id']}")
        else:
            print("  [5] Cheapest 2-Stop Flight       : N/A (No 2-Stop flights found for this route)")

        # 6. Shortest Overall Flight
        if c_sh:
            dur = c_sh.get('duration', 'N/A')
            print(f"  [6] Shortest Flight (Overall)    : {c_sh['price']:<12} | Airline: {c_sh['airline']:<20} | Duration: {dur:<7} | Offer ID: {c_sh['offer_id']}")

        # 7. Favorite Airline Cheapest
        if c_fav:
            dur = c_fav.get('duration', 'N/A')
            print(f"  [7] Favorite Airline ({fav_query:<8}) : {c_fav['price']:<12} | Airline: {c_fav['airline']:<20} | Duration: {dur:<7} | Offer ID: {c_fav['offer_id']}")
        else:
            print(f"  [7] Favorite Airline ({fav_query:<8}) : N/A (No offers found for '{fav_query}')")

        # 8. Favorite Airline Shortest Duration
        if s_fav:
            dur = s_fav.get('duration', 'N/A')
            print(f"  [8] Fav Airline Shortest ({fav_query:<8}): {s_fav['price']:<12} | Airline: {s_fav['airline']:<20} | Duration: {dur:<7} | Offer ID: {s_fav['offer_id']}")
        else:
            print(f"  [8] Fav Airline Shortest ({fav_query:<8}): N/A (No offers found for '{fav_query}')")

        print("=" * 95)

    def _export_search_results_json(
        self,
        offers: list,
        fav_airline: str = "",
        search_prompt: Optional[str] = None,
        search_params: Optional[dict[str, Any]] = None,
    ) -> str:
        """Export comprehensive search results and pre-calculated category breakdowns to a hashed JSON file."""
        if not offers:
            return ""

        from datetime import datetime

        if search_prompt is None:
            search_prompt = getattr(offers, "search_prompt", "")
        if search_params is None:
            search_params = getattr(offers, "search_params", {})

        highlights = getattr(offers, "category_highlights", None)
        if not highlights or fav_airline:
            highlights = self.client.flights.compute_category_highlights(offers, favorite_airline=fav_airline)

        def format_offer_summary(o):
            if not o:
                return None
            if isinstance(o, dict) and "departure_date" in o and "departure_time" in o:
                return o
            return self.client.flights._build_offer_summary(o)

        output_json = getattr(offers, "output_json", None)
        request_metadata = {
            "search_prompt": search_prompt or "",
            "search_params": search_params or {},
        }
        if output_json and not fav_airline:
            data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                **request_metadata,
                "category_highlights": output_json.get("category_highlights", highlights),
                "performance_metrics": self.client.http_client.get_metrics_summary(),
                "cache_metrics": self.client.cache.get_metrics_summary() if self.client.cache else {},
                "total_offers_found": len(offers),
                "cheapest_non_stop_offers": output_json.get("cheapest_non_stop_offers", []),
                "shortest_non_stop_offers": output_json.get("shortest_non_stop_offers", []),
                "top_offers": output_json.get("top_offers", [])
            }
        else:
            max_offers = getattr(self.client.config, "max_cached_offers", 40)
            max_non_stop = getattr(self.client.config, "max_non_stop_offers", 10)

            non_stop_list = getattr(offers, "non_stop_offers", None)
            if not non_stop_list:
                non_stop_list = [o for o in offers if self._get_offer_max_stops(o) == 0]

            non_stop_cheapest = sorted(non_stop_list, key=lambda o: float(getattr(o, "total_amount", 0.0) or 0.0))[:max_non_stop]
            non_stop_shortest = sorted(non_stop_list, key=lambda o: self._get_offer_total_duration_min(o))[:max_non_stop]

            data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                **request_metadata,
                "category_highlights": highlights,
                "performance_metrics": self.client.http_client.get_metrics_summary(),
                "cache_metrics": self.client.cache.get_metrics_summary() if self.client.cache else {},
                "total_offers_found": len(offers),
                "cheapest_non_stop_offers": [format_offer_summary(o) for o in non_stop_cheapest if o],
                "shortest_non_stop_offers": [format_offer_summary(o) for o in non_stop_shortest if o],
                "top_offers": [format_offer_summary(o) for o in offers[:max_offers] if o]
            }

        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)

        opt_key = getattr(offers, "opt_cache_key", None)
        import hashlib
        if opt_key and "search_optimized:" in opt_key:
            try:
                raw_json = opt_key.split("search_optimized:", 1)[1]
                params = json.loads(raw_json)
                orig = str(params.get("origin", "SEARCH")).upper()
                dest = str(params.get("destination", "")).upper()
                dep = str(params.get("target_date", ""))
                ret = str(params.get("target_return_date") or "oneway")
                min_d = str(params.get("min_duration_days", ""))
                max_d = str(params.get("max_duration_days", ""))
                cabin = str(params.get("cabin_class", "economy")).lower()
                hash_short = hashlib.md5(opt_key.encode("utf-8")).hexdigest()[:6]

                filename = f"{orig}_{dest}_{dep}_{ret}_{min_d}to{max_d}d_{cabin}_{hash_short}_search_results.json"
            except Exception:
                filename = f"{hashlib.md5(opt_key.encode('utf-8')).hexdigest()[:12]}_search_results.json"
        elif search_params and isinstance(search_params, dict) and search_params.get("origin"):
            orig = str(search_params.get("origin", "SEARCH")).upper()
            dest = str(search_params.get("destination", "")).upper()
            dep = str(search_params.get("departure_date") or search_params.get("target_date") or "")
            ret = str(search_params.get("return_date") or search_params.get("target_return_date") or "oneway")
            cabin = str(search_params.get("cabin_class", "economy")).lower()
            data_hash = hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:6]
            filename = f"{orig}_{dest}_{dep}_{ret}_{cabin}_{data_hash}_search_results.json"
        elif opt_key:
            key_hash = hashlib.md5(opt_key.encode("utf-8")).hexdigest()[:12]
            filename = f"{key_hash}_search_results.json"
        else:
            data_hash = hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]
            filename = f"{data_hash}_search_results.json"

        output_file = os.path.join(output_dir, filename)

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"\n[+] Full JSON search report saved to '{output_file}'")
        except Exception as err:
            print(f"\n[!] Error saving JSON search results: {err}")

        return output_file

    def _extract_slice_details(self, slc: Any) -> dict[str, str]:
        """Extract origin, destination, departure time, arrival time, carrier, and flight number from slice."""
        segments = getattr(slc, "segments", []) if hasattr(slc, "segments") else (slc.get("segments", []) if isinstance(slc, dict) else [])
        duration = getattr(slc, "duration", "") if hasattr(slc, "duration") else (slc.get("duration", "") if isinstance(slc, dict) else "")

        if segments:
            first_seg = segments[0]
            last_seg = segments[-1]

            def get_val(obj, attr, key, default=None):
                if hasattr(obj, attr) and getattr(obj, attr) is not None:
                    return getattr(obj, attr)
                elif isinstance(obj, dict) and key in obj:
                    return obj.get(key)
                return default

            dep_raw = get_val(first_seg, "departing_at", "departing_at", "")
            arr_raw = get_val(last_seg, "arriving_at", "arriving_at", "")

            orig_obj = get_val(first_seg, "origin", "origin", {})
            dest_obj = get_val(last_seg, "destination", "destination", {})

            orig_code = orig_obj.get("iata_code") or orig_obj.get("name") if isinstance(orig_obj, dict) else str(orig_obj or "")
            dest_code = dest_obj.get("iata_code") or dest_obj.get("name") if isinstance(dest_obj, dict) else str(dest_obj or "")

            carrier_obj = get_val(first_seg, "marketing_carrier", "marketing_carrier", {})
            carrier_name = carrier_obj.get("name", "") if isinstance(carrier_obj, dict) else str(carrier_obj or "")
            flight_no = get_val(first_seg, "flight_number", "marketing_carrier_flight_number", "")

            if len(segments) == 1:
                stops_str = "Direct (0 stops)"
            else:
                layovers = []
                for i in range(len(segments) - 1):
                    seg_arr = segments[i]
                    seg_dep = segments[i + 1]

                    arr_obj = get_val(seg_arr, "destination", "destination", {})
                    arr_iata = arr_obj.get("iata_code") or arr_obj.get("name") if isinstance(arr_obj, dict) else str(arr_obj or "")

                    arr_time = get_val(seg_arr, "arriving_at", "arriving_at", "")
                    dep_time = get_val(seg_dep, "departing_at", "departing_at", "")

                    formatted_arr = self._format_iso_time(arr_time)
                    formatted_dep = self._format_iso_time(dep_time)

                    layovers.append(f"{arr_iata} [Arr: {formatted_arr}, Dep: {formatted_dep}]")

                stops_count = len(segments) - 1
                stops_str = f"{stops_count} stop(s) via " + ", ".join(layovers)

            return {
                "origin": orig_code or "N/A",
                "destination": dest_code or "N/A",
                "departing_at": self._format_iso_time(dep_raw),
                "arriving_at": self._format_iso_time(arr_raw),
                "carrier": carrier_name,
                "flight_number": str(flight_no or ""),
                "stops": stops_str,
                "duration": f" ({duration})" if duration else ""
            }
        else:
            def get_attr(obj, key):
                return getattr(obj, key, "") if hasattr(obj, key) else (obj.get(key, "") if isinstance(obj, dict) else "")

            orig_obj = get_attr(slc, "origin")
            dest_obj = get_attr(slc, "destination")
            dep_raw = get_attr(slc, "departing_at")
            arr_raw = get_attr(slc, "arriving_at")

            orig_code = orig_obj.get("iata_code") if isinstance(orig_obj, dict) else str(orig_obj or "")
            dest_code = dest_obj.get("iata_code") if isinstance(dest_obj, dict) else str(dest_obj or "")

            return {
                "origin": orig_code or "N/A",
                "destination": dest_code or "N/A",
                "departing_at": self._format_iso_time(dep_raw),
                "arriving_at": self._format_iso_time(arr_raw),
                "carrier": "",
                "flight_number": "",
                "stops": "N/A",
                "duration": f" ({duration})" if duration else ""
            }

    def _format_iso_time(self, iso_str: str) -> str:
        if not iso_str:
            return "N/A"
        clean = str(iso_str).replace("Z", "").split(".")[0]
        if "T" in clean:
            parts = clean.split("T")
            time_part = parts[1][:5] if len(parts[1]) >= 5 else parts[1]
            return f"{parts[0]} {time_part}"
        return str(iso_str)

    def _book_flight(self, offer):
        off_id = getattr(offer, "id", "") or (offer.get("id") if isinstance(offer, dict) else "")
        off_curr = getattr(offer, "total_currency", "USD") if hasattr(offer, "total_currency") else (offer.get("total_currency", "USD") if isinstance(offer, dict) else "USD")
        off_amt = getattr(offer, "total_amount", "0.00") if hasattr(offer, "total_amount") else (offer.get("total_amount", "0.00") if isinstance(offer, dict) else "0.00")

        print(f"\n--- Booking Flight Offer {off_id} ---")
        given = prompt_input("  Passenger Given / First Name", default="John")
        family = prompt_input("  Passenger Family / Last Name", default="Doe")
        email = prompt_input("  Passenger Email", default="john.doe@example.com")
        phone = prompt_input("  Passenger Phone Number (E.164 format)", default="+14155552671")
        title = prompt_input("  Passenger Title (mr, ms, mrs, dr)", default="mr").lower()
        gender = prompt_input("  Passenger Gender (m, f)", default="m").lower()
        born_on = prompt_input("  Passenger Date of Birth (YYYY-MM-DD)", default="1990-01-01")

        print("\nSelect Order / Booking Payment Method & Type:")
        print("  [1] Hold Order (Reserve seats without immediate payment / No balance required)")
        print("  [2] Instant Order - Balance Payment (Pay with Duffel Balance)")
        print("  [3] Instant Order - Credit Card Payment (Card Token)")
        print("  [4] Instant Order - Saved Customer Card (Customer Card ID)")
        print("  [5] Instant Order - ARC / BSP One-Step Payment")
        print("  [6] Instant Order - Bank Transfer Payment")
        print("  [7] Instant Order - Instant Bank Transfer (Open Banking)")
        booking_type_choice = prompt_input("Choice [1]", default="1", required=False)

        if booking_type_choice == "2":
            order_type = "instant"
            pym_curr = prompt_input("  Payment Currency Code", default=off_curr, required=False)
            pym_amt = prompt_input("  Payment Amount", default=str(off_amt), required=False)
            payments = [Payment(type="balance", currency=pym_curr, amount=pym_amt)]
        elif booking_type_choice == "3":
            order_type = "instant"
            pym_curr = prompt_input("  Payment Currency Code", default=off_curr, required=False)
            pym_amt = prompt_input("  Payment Amount", default=str(off_amt), required=False)
            card_token = prompt_input("  Duffel Credit Card Token (Optional)", default="", required=False)
            raw_card = {"card_token": card_token} if card_token else {}
            payments = [Payment(type="card", currency=pym_curr, amount=pym_amt, raw=raw_card)]
        elif booking_type_choice == "4":
            order_type = "instant"
            pym_curr = prompt_input("  Payment Currency Code", default=off_curr, required=False)
            pym_amt = prompt_input("  Payment Amount", default=str(off_amt), required=False)
            cust_card_id = prompt_input("  Customer Card ID (e.g. 'ccrd_00001')", default="", required=False)
            raw_card = {"customer_card_id": cust_card_id} if cust_card_id else {}
            payments = [Payment(type="customer_card", currency=pym_curr, amount=pym_amt, raw=raw_card)]
        elif booking_type_choice == "5":
            order_type = "instant"
            pym_curr = prompt_input("  Payment Currency Code", default=off_curr, required=False)
            pym_amt = prompt_input("  Payment Amount", default=str(off_amt), required=False)
            payments = [Payment(type="arc_bsp_one_step", currency=pym_curr, amount=pym_amt)]
        elif booking_type_choice == "6":
            order_type = "instant"
            pym_curr = prompt_input("  Payment Currency Code", default=off_curr, required=False)
            pym_amt = prompt_input("  Payment Amount", default=str(off_amt), required=False)
            payments = [Payment(type="bank_transfer", currency=pym_curr, amount=pym_amt)]
        elif booking_type_choice == "7":
            order_type = "instant"
            pym_curr = prompt_input("  Payment Currency Code", default=off_curr, required=False)
            pym_amt = prompt_input("  Payment Amount", default=str(off_amt), required=False)
            payments = [Payment(type="instant_bank_transfer", currency=pym_curr, amount=pym_amt)]
        else:
            order_type = "hold"
            payments = []

        pax_id = "pas_00001"
        passengers_raw = getattr(offer, "passengers", []) if hasattr(offer, "passengers") else (offer.get("passengers", []) if isinstance(offer, dict) else [])
        if passengers_raw:
            p0 = passengers_raw[0]
            pax_id = p0.get("id") if isinstance(p0, dict) else getattr(p0, "id", "pas_00001")

        pax = Passenger(
            id=pax_id,
            given_name=given,
            family_name=family,
            email=email,
            phone_number=phone,
            title=title,
            gender=gender,
            born_on=born_on
        )

        print(f"\nSubmitting {order_type.upper()} booking order to Duffel API...")
        try:
            order = self.client.flights.create_order(
                selected_offers=[off_id],
                passengers=[pax],
                payments=payments,
                type=order_type
            )
            print(f"\n[+] Flight Booking Confirmed! ({order_type.upper()} ORDER)")
            print(f"  * Order ID          : {order.id}")
            print(f"  * Booking Reference : {order.booking_reference}")
            print(f"  * Total Amount      : {order.total_currency} {order.total_amount}")
            if order_type == "hold":
                print(f"  * Status            : Seat Hold Confirmed (Pay later before expiration)")
        except Exception as err:
            err_msg = str(err)
            if "insufficient_balance" in err_msg and order_type == "instant":
                print(f"\n[!] Duffel Account Balance Insufficient for Instant Payment.")
                print("    Retrying automatically with Hold Order (type='hold')...")
                try:
                    order = self.client.flights.create_order(
                        selected_offers=[off_id],
                        passengers=[pax],
                        payments=[],
                        type="hold"
                    )
                    print(f"\n[+] Flight Hold Booking Confirmed!")
                    print(f"  * Order ID          : {order.id}")
                    print(f"  * Booking Reference : {order.booking_reference}")
                    print(f"  * Total Amount      : {order.total_currency} {order.total_amount}")
                    print(f"  * Status            : Seat Hold Confirmed (Pay later before expiration)")
                except Exception as retry_err:
                    print(f"[!] Hold retry failed: {retry_err}")
            else:
                print(f"[!] Booking failed: {err}")

    def _handle_book_flight_menu(self):
        print("\n--- [FLIGHTS] Book Flight Offer ---")
        offer_id = prompt_input("Enter Flight Offer ID to book (e.g. 'off_0000B9fe...')")
        if not offer_id:
            print("Operation cancelled.")
            return

        print(f"\n🔍 Re-validating flight offer '{offer_id}' live with Duffel API...")
        try:
            offer_data = self.client.flights.get_offer(offer_id)
            if offer_data:
                from ..models.flights import FlightOffer
                offer = FlightOffer.from_dict(offer_data) if isinstance(offer_data, dict) else offer_data
                owner_name = self._get_offer_owner_name(offer)
                total_dur_min = self._get_offer_total_duration_min(offer)
                dur_str = self._format_duration(total_dur_min)
                exp_str = getattr(offer, 'expires_at', 'Valid')

                print("\n" + "=" * 85)
                print("[+] LIVE OFFER VALIDATED DETAILS:")
                print(f"  * Verified Total Price  : {offer.total_currency} {offer.total_amount}")
                print(f"  * Operating Airline     : {owner_name}")
                print(f"  * Total Travel Duration : {dur_str}")
                print(f"  * Offer Expiration      : {exp_str}")
                print(f"  * Offer ID              : {offer.id}")
                print("-" * 85)

                slices = getattr(offer, "slices", [])
                for leg_idx, slc in enumerate(slices, 1):
                    info = self._extract_slice_details(slc)
                    carrier_str = f"{info['carrier']} {info['flight_number']}".strip() or "N/A"
                    print(f"  * Leg {leg_idx} Departure  : {info['origin']} [{info['departing_at']}]")
                    print(f"  * Leg {leg_idx} Arrival    : {info['destination']} [{info['arriving_at']}]")
                    print(f"  * Leg {leg_idx} Duration   : {info['duration'].strip(' ()') or 'N/A'}")
                    print(f"  * Leg {leg_idx} Carrier    : {carrier_str}")
                    print(f"  * Leg {leg_idx} Stops      : {info['stops']}")

                    segments = getattr(slc, "segments", []) if hasattr(slc, "segments") else (slc.get("segments", []) if isinstance(slc, dict) else [])
                    if len(segments) > 1:
                        print(f"    Layover Stop Details:")
                        for s_i in range(len(segments) - 1):
                            seg_arr = segments[s_i]
                            seg_dep = segments[s_i + 1]

                            arr_obj = getattr(seg_arr, "destination", {}) if hasattr(seg_arr, "destination") else (seg_arr.get("destination", {}) if isinstance(seg_arr, dict) else {})
                            arr_name = arr_obj.get("name") or arr_obj.get("iata_code") if isinstance(arr_obj, dict) else str(arr_obj or "")
                            arr_iata = arr_obj.get("iata_code") if isinstance(arr_obj, dict) else str(arr_obj or "")

                            arr_time = getattr(seg_arr, "arriving_at", "") if hasattr(seg_arr, "arriving_at") else (seg_arr.get("arriving_at", "") if isinstance(seg_arr, dict) else "")
                            dep_time = getattr(seg_dep, "departing_at", "") if hasattr(seg_dep, "departing_at") else (seg_dep.get("departing_at", "") if isinstance(seg_dep, dict) else "")

                            print(f"      Stop {s_i + 1}: {arr_name} ({arr_iata})")
                            print(f"             Arrive Layover : {self._format_iso_time(arr_time)}")
                            print(f"             Depart Layover : {self._format_iso_time(dep_time)}")
                    print("-" * 85)
                print("=" * 85)

                self._book_flight(offer)
            else:
                print(f"\n[!] Offer '{offer_id}' is no longer available or has expired. Please run a new search (Option 1 or 2).")
        except Exception as err:
            print(f"\n[!] Live offer validation failed: {err}")
            print("    The flight offer may have sold out or expired. Please execute a fresh search (Option 1 or 2).")

    def _handle_book_stay_menu(self):
        print("\n--- [STAYS] Book Stay Offer ---")
        offer_id = prompt_input("Enter Stay Offer ID to book (e.g. 'off_stay_123')")
        if not offer_id:
            print("Operation cancelled.")
            return

        given = prompt_input("  Guest Given Name", default="John")
        family = prompt_input("  Guest Family Name", default="Doe")
        email = prompt_input("  Guest Email", default="john.doe@example.com")

        print("\nSubmitting Stay booking order to Duffel...")
        try:
            order = self.client.stays.create_order(
                quote_id=offer_id,
                guests=[{"given_name": given, "family_name": family, "email": email}],
                payments=[{"type": "balance", "currency": "USD", "amount": "100.00"}]
            )
            print(f"\n[+] Stay Booking Confirmed! Order ID: {getattr(order, 'id', 'N/A')}")
        except Exception as err:
            print(f"[!] Stay Booking failed: {err}")

    def _handle_book_car_menu(self):
        print("\n--- [CARS] Book Car Rental Offer ---")
        offer_id = prompt_input("Enter Car Offer ID to book (e.g. 'off_car_123')")
        if not offer_id:
            print("Operation cancelled.")
            return

        given = prompt_input("  Driver Given Name", default="John")
        family = prompt_input("  Driver Family Name", default="Doe")
        email = prompt_input("  Driver Email", default="john.doe@example.com")

        print("\nSubmitting Car Rental booking order to Duffel...")
        try:
            order = self.client.cars.create_order(
                offer_id=offer_id,
                driver={"given_name": given, "family_name": family, "email": email},
                payments=[{"type": "balance", "currency": "USD", "amount": "100.00"}]
            )
            print(f"\n[+] Car Rental Booking Confirmed! Order ID: {getattr(order, 'id', 'N/A')}")
        except Exception as err:
            print(f"[!] Car Booking failed: {err}")

    def _handle_stays(self):
        print("\n--- [STAYS] Hotel Search ---")
        prompt = input("\nDescribe your stay request in natural language (or press Enter for step-by-step):\n> ").strip()

        extracted = PromptExtractor.extract_stay_info(prompt) if prompt else {}
        slots = fill_stay_slots(extracted)

        print("\nStay Search Summary:")
        print(f"  * Location: {slots['location']}")
        print(f"  * Check-in: {slots['check_in_date']}")
        print(f"  * Check-out: {slots['check_out_date']}")
        print(f"  * Guests: {slots['guests_count']}")

        confirm = prompt_input("\nProceed with Stay API Search?", default="y", required=False).lower()
        if confirm not in ("y", "yes"):
            print("Cancelled search.")
            return

        print("\nContacting Duffel Stays API...")
        try:
            results = self.client.stays.search(
                check_in_date=slots['check_in_date'],
                check_out_date=slots['check_out_date'],
                rooms=slots['rooms'],
                location={"place_id": slots['location']}
            )
            print(f"\n[+] Search completed. Returned {len(results)} accommodation options.")
            print("[+] To book a stay offer, select Option 5 (Book Stay Offer) from the main menu.")
        except Exception as err:
            print(f"\n[!] Error during Stays search: {err}")

    def _handle_cars(self):
        print("\n--- [CARS] Car Rental Search ---")
        prompt = input("\nDescribe your car rental request in natural language (or press Enter for step-by-step):\n> ").strip()

        extracted = PromptExtractor.extract_car_info(prompt) if prompt else {}
        slots = fill_car_slots(extracted)

        print("\nCar Rental Search Summary:")
        print(f"  * Pickup Location: {slots['pickup_location']}")
        print(f"  * Dropoff Location: {slots['dropoff_location']}")
        print(f"  * Pickup Date: {slots['pickup_datetime']}")
        print(f"  * Dropoff Date: {slots['dropoff_datetime']}")
        print(f"  * Driver Age: {slots['driver_age']}")

        confirm = prompt_input("\nProceed with Car API Search?", default="y", required=False).lower()
        if confirm not in ("y", "yes"):
            print("Cancelled search.")
            return

        print("\nContacting Duffel Cars API...")
        try:
            offers = self.client.cars.search(
                pickup_location=slots['pickup_location'],
                dropoff_location=slots['dropoff_location'],
                pickup_datetime=slots['pickup_datetime'],
                dropoff_datetime=slots['dropoff_datetime'],
                driver_age=slots['driver_age']
            )
            print(f"\n[+] Search completed. Returned {len(offers)} car rental offers.")
            print("[+] To book a car rental offer, select Option 7 (Book Car Offer) from the main menu.")
        except Exception as err:
            print(f"\n[!] Error during Car search: {err}")

    def _handle_config(self):
        print("\n--- Configure Duffel API Key ---")
        print(f"Current Token: {self.client.config.api_token or 'None'}")
        new_token = prompt_input("Enter new Duffel API Token (duffel_test_... or duffel_live_...)")
        if new_token:
            self.client.config.api_token = new_token
            try:
                cfg = {
                    "duffel_api_token": new_token,
                    "base_url": self.client.config.base_url,
                    "api_version": self.client.config.api_version,
                    "debug": self.client.config.debug
                }
                with open("config.json", "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
                print("[+] API Token updated and saved to config.json successfully!")
            except Exception as err:
                print(f"[+] API Token updated in session (could not write config.json: {err})")


def main():
    cli = DuffelCLI()
    cli.run()


if __name__ == "__main__":
    main()
