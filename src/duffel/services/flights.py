"""
Service for Duffel Flights API.
"""

import json
from typing import Any, Optional, Union

from ..models.common import CabinClass, Passenger, Payment
from ..models.flights import (
    FlightCancellation,
    FlightOffer,
    FlightOrder,
    FlightSearchQuery,
    FlightSliceQuery,
    OfferList,
)
from .base import BaseService


class FlightsService(BaseService):
    """Integrates with Duffel REST API Air/Flights endpoints."""

    def _build_cache_key(
        self,
        slices: list[Union[FlightSliceQuery, dict[str, Any]]],
        passengers: list[Union[Passenger, dict[str, Any]]],
        cabin_class: Union[CabinClass, str] = CabinClass.ECONOMY,
        max_connections: Optional[int] = None,
    ) -> tuple[str, dict[str, Any]]:
        formatted_slices = []
        for s in slices:
            if isinstance(s, FlightSliceQuery):
                formatted_slices.append(s.to_dict())
            elif isinstance(s, dict):
                formatted_slices.append({
                    "origin": s["origin"],
                    "destination": s["destination"],
                    "departure_date": s["departure_date"],
                })

        formatted_passengers = []
        for p in passengers:
            if isinstance(p, Passenger):
                formatted_passengers.append(p.to_dict())
            elif isinstance(p, dict):
                formatted_passengers.append(p)

        cabin_val = cabin_class.value if isinstance(cabin_class, CabinClass) else str(cabin_class)

        payload: dict[str, Any] = {
            "slices": formatted_slices,
            "passengers": formatted_passengers,
            "cabin_class": cabin_val,
        }
        if max_connections is not None:
            payload["max_connections"] = max_connections

        cache_key = f"duffel:flights:search:{json.dumps(payload, sort_keys=True)}"
        return cache_key, payload

    def search(
        self,
        slices: list[Union[FlightSliceQuery, dict[str, Any]]],
        passengers: list[Union[Passenger, dict[str, Any]]],
        cabin_class: Union[CabinClass, str] = CabinClass.ECONOMY,
        max_connections: Optional[int] = None,
        return_offers: bool = True,
        force_refresh: bool = False,
    ) -> Union[list[FlightOffer], dict[str, Any]]:
        """
        Search for flight offers across given slices.

        Endpoint: POST /air/offer_requests
        """
        cache_key, payload = self._build_cache_key(
            slices=slices,
            passengers=passengers,
            cabin_class=cabin_class,
            max_connections=max_connections,
        )

    def _build_offer_summary(self, offer: Any) -> Optional[dict[str, Any]]:
        """Construct a standardized summary dict for a flight offer."""
        if not offer:
            return None

        if isinstance(offer, dict):
            amt = offer.get("total_amount", "0.00")
            curr = offer.get("total_currency", "USD")
            owner_dict = offer.get("owner", {})
            owner = owner_dict.get("name") or owner_dict.get("iata_code") if isinstance(owner_dict, dict) else "Airline"
            slices = offer.get("slices", [])
            o_id = offer.get("id", "")
        else:
            amt = getattr(offer, "total_amount", "0.00")
            curr = getattr(offer, "total_currency", "USD")
            owner_dict = getattr(offer, "owner", {})
            owner = owner_dict.get("name") or owner_dict.get("iata_code") if isinstance(owner_dict, dict) else "Airline"
            slices = getattr(offer, "slices", [])
            o_id = getattr(offer, "id", "")

        max_stops = 0
        total_dur_min = 0

        for slc in slices:
            if isinstance(slc, dict):
                segs = slc.get("segments", [])
                dur_str = slc.get("duration", "")
            else:
                segs = getattr(slc, "segments", [])
                dur_str = getattr(slc, "duration", "")

            stops = max(0, len(segs) - 1)
            if stops > max_stops:
                max_stops = stops

            if dur_str and isinstance(dur_str, str):
                import re
                h_match = re.search(r"(\d+)H", dur_str)
                m_match = re.search(r"(\d+)M", dur_str)
                hours = int(h_match.group(1)) if h_match else 0
                mins = int(m_match.group(1)) if m_match else 0
                parsed_min = hours * 60 + mins
                if parsed_min > 0:
                    total_dur_min += parsed_min

        dur_str_formatted = "N/A"
        if total_dur_min > 0:
            h = total_dur_min // 60
            m = total_dur_min % 60
            dur_str_formatted = f"{h}h {m}m" if (h > 0 and m > 0) else (f"{h}h" if h > 0 else f"{m}m")

        return {
            "offer_id": o_id,
            "price": f"{curr} {amt}",
            "total_amount": float(amt or 0.0),
            "currency": curr,
            "airline": owner or "Airline",
            "max_stops": max_stops,
            "duration": dur_str_formatted,
            "duration_minutes": total_dur_min if total_dur_min > 0 else None,
        }

    def _is_us_domestic(self, origin_code: str, dest_code: str) -> bool:
        """Check if both origin and destination are US domestic airport IATA codes."""
        us_airports = {
            "ATL", "LAX", "ORD", "DFW", "DEN", "JFK", "SFO", "SEA", "LAS", "MCO",
            "EWR", "CLT", "PHX", "IAH", "MIA", "BOS", "MSP", "FLL", "DTW", "PHL",
            "LGA", "BWI", "SLC", "SAN", "IAD", "DCA", "MDW", "TPA", "PDX", "HNL",
            "BNA", "AUS", "STL", "SJC", "MSY", "RDU", "SJU", "SMF", "SNA", "CLE",
            "SAT", "PIT", "CVG", "IND", "CMH", "OGG", "PBI", "RSW", "JAX", "ABQ",
            "BUF", "OAK", "ANC", "BUR", "ONT", "MEM", "RIC", "PVD", "GRR", "OKC",
            "BOI", "ORF", "CHS", "OMA", "TUL", "GEG", "LIT", "SDF", "TUS", "FAT"
        }
        return (origin_code.upper() in us_airports) and (dest_code.upper() in us_airports)

    def _determine_default_favorite_airline(self, offers: list) -> str:
        """Default to Frontier for US domestic travel, Delta for international travel, falling back to top returned carrier."""
        if not offers:
            return "Delta"

        target_default = "Delta"
        sample = offers[0]
        slices = getattr(sample, "slices", []) if hasattr(sample, "slices") else (sample.get("slices", []) if isinstance(sample, dict) else [])
        if slices:
            first_slc = slices[0]
            if isinstance(first_slc, dict):
                orig_dict = first_slc.get("origin", {})
                dest_dict = first_slc.get("destination", {})
                orig = orig_dict.get("iata_code") if isinstance(orig_dict, dict) else str(orig_dict)
                dest = dest_dict.get("iata_code") if isinstance(dest_dict, dict) else str(dest_dict)
            else:
                orig_dict = getattr(first_slc, "origin", {})
                dest_dict = getattr(first_slc, "destination", {})
                orig = orig_dict.get("iata_code") if isinstance(orig_dict, dict) else str(orig_dict)
                dest = dest_dict.get("iata_code") if isinstance(dest_dict, dict) else str(dest_dict)

            if orig and dest and self._is_us_domestic(orig, dest):
                target_default = "Frontier"

        # Check if target_default is present in the offers
        t_low = target_default.lower()
        for o in offers:
            sum_dict = self._build_offer_summary(o)
            if sum_dict and t_low in sum_dict.get("airline", "").lower():
                return target_default

        # Fallback to the airline of the cheapest overall offer
        cheapest_sum = self._build_offer_summary(offers[0])
        if cheapest_sum and cheapest_sum.get("airline"):
            return cheapest_sum.get("airline")

        return target_default

    def compute_all_airline_highlights(self, raw_offers: list) -> dict[str, Any]:
        """
        Scan ALL raw offers returned from Duffel API and pre-compute the cheapest
        and shortest offer for EVERY airline present in the response.
        """
        if not raw_offers:
            return {}

        summaries = [self._build_offer_summary(o) for o in raw_offers if o]
        summaries = [s for s in summaries if s is not None]

        if not summaries:
            return {}

        airline_map: dict[str, list] = {}
        for s in summaries:
            airline_name = s.get("airline", "Airline")
            airline_key = airline_name.strip().lower()
            if airline_key not in airline_map:
                airline_map[airline_key] = []
            airline_map[airline_key].append(s)

        results: dict[str, Any] = {}
        for key, offer_list in airline_map.items():
            offer_list.sort(key=lambda s: s["total_amount"])
            cheapest = offer_list[0]

            with_dur = [s for s in offer_list if s.get("duration_minutes") is not None]
            shortest = min(with_dur, key=lambda s: s["duration_minutes"]) if with_dur else offer_list[0]

            airline_display_name = cheapest.get("airline", key.title())

            results[key] = {
                "airline_name": airline_display_name,
                "cheapest": cheapest,
                "shortest": shortest
            }

        return results

    def compute_category_highlights(
        self,
        offers: list,
        favorite_airline: str = "",
        all_airline_highlights: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Compute pre-calculated category highlights for a list of offers."""
        if not offers:
            return {}

        summaries = [self._build_offer_summary(o) for o in offers if o]
        summaries = [s for s in summaries if s is not None]

        if not summaries:
            return {}

        summaries.sort(key=lambda s: s["total_amount"])

        cheapest_all = summaries[0]

        non_stops = [s for s in summaries if s["max_stops"] == 0]
        cheapest_non_stop = non_stops[0] if non_stops else None
        non_stops_dur = [s for s in non_stops if s["duration_minutes"] is not None]
        shortest_non_stop = min(non_stops_dur, key=lambda s: s["duration_minutes"]) if non_stops_dur else cheapest_non_stop

        one_stops = [s for s in summaries if s["max_stops"] == 1]
        cheapest_1stop = one_stops[0] if one_stops else None

        two_stops = [s for s in summaries if s["max_stops"] >= 2]
        cheapest_2stop = two_stops[0] if two_stops else None

        with_dur = [s for s in summaries if s["duration_minutes"] is not None]
        shortest_flight = min(with_dur, key=lambda s: s["duration_minutes"]) if with_dur else summaries[0]

        default_fav = self._determine_default_favorite_airline(offers)
        fav_query = (favorite_airline.strip() if favorite_airline and favorite_airline.strip() else default_fav).lower()

        cheapest_fav = None
        shortest_fav = None
        fav_airline_display = fav_query.title()

        # 1. Look up in all_airline_highlights (computed across ALL raw API offers)
        if all_airline_highlights and isinstance(all_airline_highlights, dict):
            matched_entry = None
            for key, entry in all_airline_highlights.items():
                if fav_query in key or key in fav_query:
                    matched_entry = entry
                    break
            if matched_entry:
                fav_airline_display = matched_entry.get("airline_name", fav_airline_display)
                cheapest_fav = matched_entry.get("cheapest")
                shortest_fav = matched_entry.get("shortest")

        # 2. Fallback to scanning summaries if not found in all_airline_highlights
        if not cheapest_fav:
            fav_summaries = [s for s in summaries if fav_query in s["airline"].lower()]
            if fav_summaries:
                fav_airline_display = fav_summaries[0]["airline"]
                cheapest_fav = fav_summaries[0]
                shortest_fav = (
                    min([s for s in fav_summaries if s["duration_minutes"] is not None], key=lambda s: s["duration_minutes"])
                    if [s for s in fav_summaries if s["duration_minutes"] is not None]
                    else fav_summaries[0]
                )

        return {
            "overall_cheapest": cheapest_all,
            "cheapest_non_stop": cheapest_non_stop,
            "shortest_non_stop": shortest_non_stop,
            "cheapest_1_stop": cheapest_1stop,
            "cheapest_2_stop": cheapest_2stop,
            "shortest_flight": shortest_flight,
            "favorite_airline_cheapest": {
                "favorite_airline": fav_airline_display,
                "offer": cheapest_fav
            },
            "favorite_airline_shortest": {
                "favorite_airline": fav_airline_display,
                "offer": shortest_fav
            }
        }

    def _is_non_stop(self, offer: Any) -> bool:
        """Check if an offer is a non-stop (0 stops) flight across all slices."""
        if not offer:
            return False
        slices = getattr(offer, "slices", []) if hasattr(offer, "slices") else (offer.get("slices", []) if isinstance(offer, dict) else [])
        for slc in slices:
            segs = getattr(slc, "segments", []) if hasattr(slc, "segments") else (slc.get("segments", []) if isinstance(slc, dict) else [])
            if len(segs) > 1:
                return False
        return True

    def search(
        self,
        slices: list[Union[FlightSliceQuery, dict[str, Any]]],
        passengers: list[Union[Passenger, dict[str, Any]]],
        cabin_class: Union[CabinClass, str] = CabinClass.ECONOMY,
        max_connections: Optional[int] = None,
        return_offers: bool = True,
        force_refresh: bool = False,
    ) -> Union[dict[str, Any], list[FlightOffer]]:
        """
        Execute flight search request.
        """
        cache_key, payload = self._build_cache_key(
            slices=slices,
            passengers=passengers,
            cabin_class=cabin_class,
            max_connections=max_connections,
        )

        max_offers = getattr(self.client.config, "max_cached_offers", 30)

        # 1. Check cache before calling Duffel API (unless force_refresh=True)
        if self.cache and self.cache.enabled and not force_refresh:
            cached_data = self.cache.get(cache_key)
            if cached_data is not None:
                if return_offers and "offers" in cached_data:
                    raw_offers = cached_data["offers"]
                    from datetime import datetime, timezone
                    now_iso = datetime.now(timezone.utc).isoformat()
                    valid_raw_offers = []
                    for o in raw_offers:
                        exp = o.get("expires_at")
                        if not exp or exp > now_iso:
                            valid_raw_offers.append(o)

                    if valid_raw_offers:
                        valid_raw_offers.sort(key=lambda o: float(o.get("total_amount") or 0.0))
                        all_airline_highlights = cached_data.get("airline_highlights", {})
                        highlights = cached_data.get("category_highlights") or self.compute_category_highlights(
                            valid_raw_offers[:max_offers],
                            all_airline_highlights=all_airline_highlights
                        )
                        output_json = cached_data.get("output_json")
                        non_stop_cached = cached_data.get("non_stop_offers")
                        offers = OfferList([FlightOffer.from_dict(o) for o in valid_raw_offers[:max_offers]], category_highlights=highlights)
                        setattr(offers, "airline_highlights", all_airline_highlights)
                        if output_json:
                            setattr(offers, "output_json", output_json)
                        if non_stop_cached:
                            setattr(offers, "non_stop_offers", [FlightOffer.from_dict(o) for o in non_stop_cached])
                        return offers
                else:
                    return cached_data

        # 2. Cache MISS / Force Refresh -> execute HTTP POST request to Duffel API
        params = {"return_offers": "true" if return_offers else "false"}
        response = self.client.post("/air/offer_requests", data={"data": payload}, params=params)
        data = response.get("data", {})

        req_id = data.get("id")
        if return_offers and req_id and not data.get("offers"):
            offers_res = self.client.get(
                "/air/offers",
                params={"offer_request_id": req_id, "sort": "total_amount", "limit": str(max_offers)}
            )
            if isinstance(offers_res, dict) and isinstance(offers_res.get("data"), list):
                data["offers"] = offers_res["data"]

        max_offers = getattr(self.client.config, "max_cached_offers", 40)
        max_non_stop = getattr(self.client.config, "max_non_stop_offers", 10)

        # 3. Create or replace updated response value in Redis cache to maintain fresh data
        if self.cache and self.cache.enabled and data:
            if isinstance(data, dict) and "offers" in data and isinstance(data["offers"], list):
                raw_offers = list(data["offers"])
                all_airline_highlights = self.compute_all_airline_highlights(raw_offers)

                raw_offers.sort(key=lambda o: float(o.get("total_amount") or 0.0))
                non_stop_raw = [o for o in raw_offers if self._is_non_stop(o)]
                non_stop_raw.sort(key=lambda o: float(o.get("total_amount") or 0.0))
                top_non_stop = non_stop_raw[:max_non_stop]

                # Merge top overall offers and non-stop offers into a single combined list, de-duplicating by ID
                combined_raw = list(raw_offers[:max_offers])
                cached_ids = set(o.get("id") for o in combined_raw if isinstance(o, dict))
                for ns in top_non_stop:
                    ns_id = ns.get("id") if isinstance(ns, dict) else None
                    if ns_id and ns_id not in cached_ids:
                        combined_raw.append(ns)
                        cached_ids.add(ns_id)

                # Sort combined list strictly by price ascending
                combined_raw.sort(key=lambda o: float(o.get("total_amount") or 0.0))

                highlights = self.compute_category_highlights(
                    combined_raw,
                    all_airline_highlights=all_airline_highlights
                )

                non_stop_summaries = [self._build_offer_summary(o) for o in top_non_stop if o]
                non_stop_summaries = [s for s in non_stop_summaries if s is not None]
                shortest_non_stop_summaries = sorted(non_stop_summaries, key=lambda s: s.get("duration_minutes") or 99999)

                output_json = {
                    "category_highlights": highlights,
                    "airline_highlights": all_airline_highlights,
                    "cheapest_non_stop_offers": non_stop_summaries,
                    "shortest_non_stop_offers": shortest_non_stop_summaries,
                    "top_offers": [self._build_offer_summary(o) for o in combined_raw if o]
                }

                data_to_cache = {
                    "id": data.get("id"),
                    "offers": combined_raw,
                    "non_stop_offers": top_non_stop,
                    "category_highlights": highlights,
                    "airline_highlights": all_airline_highlights,
                    "output_json": output_json
                }
            else:
                data_to_cache = data
            self.cache.set(cache_key, data_to_cache)

        if return_offers and "offers" in data:
            raw_offers = list(data["offers"])
            all_airline_highlights = self.compute_all_airline_highlights(raw_offers)
            offers = [FlightOffer.from_dict(o) for o in raw_offers]
            offers.sort(key=lambda o: float(o.total_amount or 0.0))

            non_stop_objs = [o for o in offers if self._is_non_stop(o)]
            non_stop_objs.sort(key=lambda o: float(o.total_amount or 0.0))
            top_non_stop_objs = non_stop_objs[:max_non_stop]

            combined_objs = list(offers[:max_offers])
            cached_ids = set(getattr(o, "id", "") for o in combined_objs)
            for ns in top_non_stop_objs:
                ns_id = getattr(ns, "id", "")
                if ns_id and ns_id not in cached_ids:
                    combined_objs.append(ns)
                    cached_ids.add(ns_id)

            combined_objs.sort(key=lambda o: float(o.total_amount or 0.0))

            highlights = self.compute_category_highlights(
                combined_objs,
                all_airline_highlights=all_airline_highlights
            )
            res_list = OfferList(combined_objs, category_highlights=highlights)
            setattr(res_list, "airline_highlights", all_airline_highlights)
            setattr(res_list, "non_stop_offers", top_non_stop_objs)
            return res_list
        return data

    def get_offer_request(self, offer_request_id: str) -> dict[str, Any]:
        """
        Retrieve details of an offer request.

        Endpoint: GET /air/offer_requests/{id}
        """
        res = self.client.get(f"/air/offer_requests/{offer_request_id}")
        return res.get("data", {})

    def list_offers(
        self,
        offer_request_id: str,
        sort: Optional[str] = None,
        max_connections: Optional[int] = None,
    ) -> list[FlightOffer]:
        """
        List offers associated with an offer request.

        Endpoint: GET /air/offers
        """
        params: dict[str, Any] = {"offer_request_id": offer_request_id}
        if sort:
            params["sort"] = sort
        if max_connections is not None:
            params["max_connections"] = max_connections

        res = self.client.get("/air/offers", params=params)
        raw_offers = res.get("data", [])
        return [FlightOffer.from_dict(o) for o in raw_offers]

    def get_offer(self, offer_id: str) -> FlightOffer:
        """
        Retrieve a single flight offer by ID.

        Endpoint: GET /air/offers/{id}
        """
        res = self.client.get(f"/air/offers/{offer_id}")
        return FlightOffer.from_dict(res.get("data", {}))

    def create_order(
        self,
        selected_offers: list[str],
        passengers: list[Union[Passenger, dict[str, Any]]],
        payments: list[Union[Payment, dict[str, Any]]],
        type: str = "instant",
    ) -> FlightOrder:
        """
        Create a flight booking order.

        Endpoint: POST /air/orders
        """
        formatted_passengers = []
        for p in passengers:
            if isinstance(p, Passenger):
                formatted_passengers.append(p.to_dict())
            else:
                formatted_passengers.append(p)

        formatted_payments = []
        for pym in payments:
            if isinstance(pym, Payment):
                formatted_payments.append(pym.to_dict())
            else:
                formatted_payments.append(pym)

        payload = {
            "type": type,
            "selected_offers": selected_offers,
            "passengers": formatted_passengers,
            "payments": formatted_payments,
        }

        res = self.client.post("/air/orders", data={"data": payload})
        return FlightOrder.from_dict(res.get("data", {}))

    def get_order(self, order_id: str) -> FlightOrder:
        """
        Retrieve order details.

        Endpoint: GET /air/orders/{id}
        """
        res = self.client.get(f"/air/orders/{order_id}")
        return FlightOrder.from_dict(res.get("data", {}))

    def list_orders(self, limit: int = 50) -> list[FlightOrder]:
        """
        List booked flight orders.

        Endpoint: GET /air/orders
        """
        res = self.client.get("/air/orders", params={"limit": limit})
        raw_orders = res.get("data", [])
        return [FlightOrder.from_dict(o) for o in raw_orders]

    def cancel_order(self, order_id: str) -> FlightCancellation:
        """
        Cancel a booked order.

        Endpoint: POST /air/order_cancellations or POST /air/orders/{id}/actions/cancel
        """
        payload = {"order_id": order_id}
        res = self.client.post("/air/order_cancellations", data={"data": payload})
        return FlightCancellation.from_dict(res.get("data", {}))

    def calculate_candidate_queries(
        self,
        origin: str,
        destination: str,
        target_date: str,
        target_return_date: Optional[str] = None,
        min_duration_days: int = 4,
        max_duration_days: int = 7,
        flex_days: int = 0,
    ) -> list[tuple[str, str, int]]:
        """
        Calculate candidate (departure_date, return_date, duration_days) tuples
        that will be queried by search_optimized.
        """
        from datetime import datetime, timedelta

        try:
            base_dep_dt = datetime.strptime(target_date, "%Y-%m-%d")
        except Exception:
            base_dep_dt = datetime.now() + timedelta(days=30)

        if target_return_date:
            try:
                base_ret_dt = datetime.strptime(target_return_date, "%Y-%m-%d")
            except Exception:
                base_ret_dt = base_dep_dt + timedelta(days=7)
        else:
            base_ret_dt = base_dep_dt + timedelta(days=7)

        now_dt = datetime.now()
        if min_duration_days > max_duration_days:
            min_duration_days, max_duration_days = max_duration_days, min_duration_days

        start_dep_dt = base_dep_dt - timedelta(days=flex_days)
        end_ret_dt = base_ret_dt + timedelta(days=flex_days)

        queries = []
        seen_pairs = set()

        curr_dep = start_dep_dt
        while curr_dep <= end_ret_dt - timedelta(days=min_duration_days):
            if curr_dep >= now_dt:
                dep_str = curr_dep.strftime("%Y-%m-%d")
                for dur in range(min_duration_days, max_duration_days + 1):
                    ret_d = curr_dep + timedelta(days=dur)
                    if ret_d > end_ret_dt:
                        break
                    ret_str = ret_d.strftime("%Y-%m-%d")
                    pair_key = (dep_str, ret_str)
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        queries.append((dep_str, ret_str, dur))
            curr_dep += timedelta(days=1)

        return queries

    def analyze_candidate_queries(
        self,
        origin: str,
        destination: str,
        target_date: str,
        target_return_date: Optional[str] = None,
        min_duration_days: int = 4,
        max_duration_days: int = 7,
        flex_days: int = 0,
        passengers: Optional[list[Union[Passenger, dict[str, Any]]]] = None,
        cabin_class: Union[CabinClass, str] = CabinClass.ECONOMY,
    ) -> dict[str, Any]:
        """
        Pre-analyze candidate queries to determine how many Duffel API calls vs Redis Cache hits will be executed.
        Checks Tier-1 Aggregated Multi-Day Cache first!
        """
        opt_cache_key = self._build_optimized_cache_key(
            origin=origin,
            destination=destination,
            target_date=target_date,
            target_return_date=target_return_date,
            min_duration_days=min_duration_days,
            max_duration_days=max_duration_days,
            flex_days=flex_days,
            passengers=passengers,
            cabin_class=cabin_class
        )

        is_tier1_cached = self.cache.exists(opt_cache_key) if (self.cache and self.cache.enabled) else False
        if is_tier1_cached:
            return {
                "is_tier1_hit": True,
                "tier1_cache_key": opt_cache_key,
                "total_batches": 1,
                "duffel_api_calls": 0,
                "redis_cache_hits": 1,
                "aggregated_cache_hits": 1,
                "individual_cache_hits": 0,
                "details": [
                    (target_date, target_return_date or "N/A", "Full Multi-Day Search", True, "Tier-1 Aggregated Redis HIT (1 Read / 0ms)")
                ],
            }

        candidate_queries = self.calculate_candidate_queries(
            origin=origin,
            destination=destination,
            target_date=target_date,
            target_return_date=target_return_date,
            min_duration_days=min_duration_days,
            max_duration_days=max_duration_days,
            flex_days=flex_days,
        )

        details = []
        redis_hits = 0
        duffel_calls = 0

        for dep_str, ret_str, dur in candidate_queries:
            q_slices = [
                FlightSliceQuery(origin=origin, destination=destination, departure_date=dep_str),
                FlightSliceQuery(origin=destination, destination=origin, departure_date=ret_str),
            ]
            cache_key, _ = self._build_cache_key(
                slices=q_slices,
                passengers=passengers if passengers else [Passenger(type="adult")],
                cabin_class=cabin_class,
            )
            is_cached = self.cache.exists(cache_key) if (self.cache and self.cache.enabled) else False
            if is_cached:
                redis_hits += 1
                status = "Tier-2 Individual Redis HIT"
            else:
                duffel_calls += 1
                status = "Duffel API Call"

            details.append((dep_str, ret_str, dur, is_cached, status))

        return {
            "is_tier1_hit": False,
            "tier1_cache_key": opt_cache_key,
            "total_batches": len(candidate_queries),
            "duffel_api_calls": duffel_calls,
            "redis_cache_hits": redis_hits,
            "aggregated_cache_hits": 0,
            "individual_cache_hits": redis_hits,
            "details": details,
        }

    def _build_optimized_cache_key(
        self,
        origin: str,
        destination: str,
        target_date: str,
        target_return_date: Optional[str] = None,
        min_duration_days: int = 7,
        max_duration_days: int = 14,
        flex_days: int = 3,
        passengers: Optional[list[Any]] = None,
        cabin_class: Any = "economy"
    ) -> str:
        """Build deterministic Redis key for Tier-1 aggregated multi-day search."""
        import json
        p_list = passengers or [Passenger(type="adult")]
        passengers_payload = [
            {"type": getattr(p, "type", p.get("type", "adult") if isinstance(p, dict) else "adult")}
            for p in p_list
        ]
        cabin_str = getattr(cabin_class, "value", str(cabin_class)).lower()
        key_payload = {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "target_date": target_date,
            "target_return_date": target_return_date,
            "min_duration_days": min_duration_days,
            "max_duration_days": max_duration_days,
            "flex_days": flex_days,
            "cabin_class": cabin_str,
            "passengers": passengers_payload
        }
        key_json = json.dumps(key_payload, sort_keys=True)
        return f"duffel:flights:search_optimized:{key_json}"

    def search_optimized(
        self,
        origin: str,
        destination: str,
        target_date: str,
        target_return_date: Optional[str] = None,
        min_duration_days: int = 4,
        max_duration_days: int = 9,
        flex_days: int = 0,
        passengers: Optional[list[Union[Passenger, dict[str, Any]]]] = None,
        cabin_class: Union[CabinClass, str] = CabinClass.ECONOMY,
        force_refresh: bool = False,
        progress_callback: Optional[Any] = None,
    ) -> list[FlightOffer]:
        """
        Search for cheapest flights within a flexible date window and trip duration range.

        - Bounded strictly by window start and end dates
        - Bounded by trip duration: min_duration_days <= duration <= max_duration_days
        - Filters candidates where min_duration_days <= trip duration <= max_duration_days
        - Queries candidates concurrently in parallel worker threads
        - Returns top 10 cheapest offers sorted strictly from lowest to highest price.
        """
        import time
        from datetime import datetime, timedelta
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if passengers is None:
            passengers = [Passenger(type="adult")]

        self.client.clear_metrics()
        search_start_time = time.perf_counter()

        opt_cache_key = self._build_optimized_cache_key(
            origin=origin,
            destination=destination,
            target_date=target_date,
            target_return_date=target_return_date,
            min_duration_days=min_duration_days,
            max_duration_days=max_duration_days,
            flex_days=flex_days,
            passengers=passengers,
            cabin_class=cabin_class
        )

        # 1. Tier-1 Aggregated Multi-Day Search Cache Check (1-Read Instant Cache Hit)
        if self.cache and self.cache.enabled and not force_refresh:
            cached_opt = self.cache.get(opt_cache_key)
            if cached_opt is not None and isinstance(cached_opt, dict) and "offers" in cached_opt:
                raw_offers = cached_opt["offers"]
                from datetime import datetime, timezone
                now_iso = datetime.now(timezone.utc).isoformat()
                valid_raw_offers = [o for o in raw_offers if isinstance(o, dict) and (not o.get("expires_at") or o.get("expires_at") > now_iso)]
                if valid_raw_offers:
                    max_offers = getattr(self.client.config, "max_cached_offers", 40)
                    all_airline_highlights = cached_opt.get("airline_highlights", {})
                    highlights = cached_opt.get("category_highlights") or self.compute_category_highlights(
                        valid_raw_offers, all_airline_highlights=all_airline_highlights
                    )
                    output_json = cached_opt.get("output_json")
                    non_stop_cached = cached_opt.get("non_stop_offers", [])

                    offers = OfferList([FlightOffer.from_dict(o) for o in valid_raw_offers[:max_offers]], category_highlights=highlights)
                    setattr(offers, "airline_highlights", all_airline_highlights)
                    setattr(offers, "opt_cache_key", opt_cache_key)
                    if output_json:
                        setattr(offers, "output_json", output_json)
                    if non_stop_cached:
                        setattr(offers, "non_stop_offers", [FlightOffer.from_dict(o) for o in non_stop_cached])

                    if progress_callback:
                        progress_callback("\n" + "=" * 65)
                        progress_callback("  REDIS & CACHE PERFORMANCE METRICS (TIER-1 AGGREGATED HIT):")
                        progress_callback("  * Cache Backend Status        : Enabled (Redis)")
                        progress_callback("  * Total Cache Reads           : 1")
                        progress_callback("  * Cache Hits (Served 0ms)     : 1 (100.0%)")
                        progress_callback("  * Cache Misses (API Calls)    : 0 (0.0%)")
                        progress_callback(f"  * Tier-1 Aggregated Key       : {opt_cache_key}")
                        progress_callback("=" * 65)
                    return offers
        try:
            base_dep_dt = datetime.strptime(target_date, "%Y-%m-%d")
        except Exception:
            base_dep_dt = datetime.now() + timedelta(days=30)

        if target_return_date:
            try:
                base_ret_dt = datetime.strptime(target_return_date, "%Y-%m-%d")
            except Exception:
                base_ret_dt = base_dep_dt + timedelta(days=7)
        else:
            base_ret_dt = base_dep_dt + timedelta(days=7)

        now_dt = datetime.now()
        if min_duration_days > max_duration_days:
            min_duration_days, max_duration_days = max_duration_days, min_duration_days

        start_dep_dt = base_dep_dt - timedelta(days=flex_days)
        end_ret_dt = base_ret_dt + timedelta(days=flex_days)

        # Build candidate (dep, ret) query pairs bounded by window and trip duration
        queries = []
        seen_pairs = set()

        curr_dep = start_dep_dt
        while curr_dep <= end_ret_dt - timedelta(days=min_duration_days):
            if curr_dep >= now_dt:
                dep_str = curr_dep.strftime("%Y-%m-%d")
                for dur in range(min_duration_days, max_duration_days + 1):
                    ret_d = curr_dep + timedelta(days=dur)
                    if ret_d > end_ret_dt:
                        break
                    ret_str = ret_d.strftime("%Y-%m-%d")
                    pair_key = (dep_str, ret_str)
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        slices = [
                            FlightSliceQuery(origin=origin, destination=destination, departure_date=dep_str),
                            FlightSliceQuery(origin=destination, destination=origin, departure_date=ret_str),
                        ]
                        queries.append(slices)
            curr_dep += timedelta(days=1)

        total_queries = len(queries)
        if progress_callback:
            progress_callback(
                f"[+] Generated {total_queries} constrained candidate batches for trip duration {min_duration_days} to {max_duration_days} days.\n"
            )

        def _execute_single(idx: int, q_slices: list):
            q_start = time.perf_counter()
            dep_date = q_slices[0].departure_date
            ret_date = q_slices[1].departure_date if len(q_slices) > 1 else "N/A"
            dur_days = "N/A"
            if len(q_slices) > 1:
                try:
                    d1 = datetime.strptime(dep_date, "%Y-%m-%d")
                    d2 = datetime.strptime(ret_date, "%Y-%m-%d")
                    dur_days = str((d2 - d1).days)
                except Exception:
                    pass

            cache_key, _ = self._build_cache_key(
                slices=q_slices,
                passengers=passengers,
                cabin_class=cabin_class,
            )
            is_cached = self.cache.exists(cache_key) if (self.cache and self.cache.enabled) else False

            if progress_callback:
                action_str = "Fetching from Redis Cache" if is_cached else "Executing Duffel API call"
                progress_callback(
                    f"  [--->] [Batch {idx}/{total_queries}] {action_str} for Outbound: {dep_date} | Return: {ret_date} ({dur_days}-day trip)..."
                )

            offers_found = []
            err_msg = None

            # Retry up to 3 times on transient rate limit / network errors
            for attempt in range(3):
                try:
                    res = self.search(slices=q_slices, passengers=passengers, cabin_class=cabin_class, return_offers=True)
                    if isinstance(res, list):
                        offers_found = res
                        err_msg = None
                        break
                except Exception as e:
                    err_msg = str(e)
                    time.sleep(0.4 * (attempt + 1))

            q_elapsed_ms = (time.perf_counter() - q_start) * 1000.0

            if progress_callback:
                if offers_found:
                    best_offer = min(offers_found, key=lambda o: float(getattr(o, "total_amount", 0.0) or 0.0))
                    best_str = f"Best Price: {best_offer.total_currency} {best_offer.total_amount} ({len(offers_found)} offers found)"
                elif err_msg:
                    best_str = f"Failed: {err_msg}"
                else:
                    best_str = "No offers returned"

                source_label = "Redis Cache (HIT)" if is_cached else "Duffel API (Cache MISS -> Saved to Redis)"
                progress_callback(
                    f"  [Batch {idx}/{total_queries}] {source_label} loaded in {q_elapsed_ms:.1f}ms | {best_str}\n"
                )

            return offers_found

        all_offers: list[FlightOffer] = []

        # Execute candidate date queries concurrently with max_workers=4 to prevent API rate limiting
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(_execute_single, idx, q_slices)
                for idx, q_slices in enumerate(queries, 1)
            ]
            for future in as_completed(futures):
                try:
                    res = future.result()
                    if isinstance(res, list):
                        all_offers.extend(res)
                except Exception:
                    pass

        # Deduplicate and sort all offers by total price ascending
        seen_ids = set()
        unique_offers = []
        for o in all_offers:
            o_id = getattr(o, "id", None)
            if o_id and o_id not in seen_ids:
                seen_ids.add(o_id)
                unique_offers.append(o)
            elif not o_id:
                unique_offers.append(o)

        unique_offers.sort(key=lambda o: float(getattr(o, "total_amount", 0.0) or 0.0))

        # Metrics summary
        total_wall_sec = time.perf_counter() - search_start_time
        metrics = self.client.get_metrics_summary()
        cache_metrics = self.cache.get_metrics_summary() if self.cache else {}

        # Record per-search metrics event
        best_price_str = f"{unique_offers[0].total_currency} {unique_offers[0].total_amount}" if unique_offers else "N/A"
        search_event = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "route": f"{origin} -> {destination}",
            "target_date": target_date,
            "target_return_date": target_return_date or "N/A",
            "duration_range": f"{min_duration_days} to {max_duration_days} days",
            "total_batches": total_queries,
            "api_calls": metrics.get("total_calls", 0),
            "cache_hits": cache_metrics.get("hits", 0),
            "hit_percentage": cache_metrics.get("hit_percentage", 0.0),
            "cheapest_price": best_price_str,
            "wall_clock_sec": round(total_wall_sec, 2),
        }
        if self.cache:
            self.cache.record_search_event(search_event)

        if progress_callback:
            progress_callback("\n" + "=" * 65)
            progress_callback("DUFFEL API METRICS & RESPONSE PERFORMANCE")
            progress_callback("=" * 65)
            progress_callback(f"  * Total Duffel API Calls Made : {metrics['total_calls']}")
            progress_callback(f"  * Min Response Latency        : {metrics['min_ms']:.1f} ms")
            progress_callback(f"  * Max Response Latency        : {metrics['max_ms']:.1f} ms")
            progress_callback(f"  * Avg Response Latency        : {metrics['avg_ms']:.1f} ms")
            progress_callback(f"  * Total Wall Clock Time       : {total_wall_sec:.2f} s (Parallel Batched)")
            if cache_metrics and cache_metrics.get("enabled"):
                backend_str = f"Redis ({cache_metrics['redis_host']})" if cache_metrics.get("backend") == "redis" else "In-Memory Fallback"
                t1_hits = cache_metrics.get("tier1_hits", 0)
                t2_hits = cache_metrics.get("tier2_hits", 0)
                progress_callback("  ---------------------------------------------------------------")
                progress_callback("  REDIS & CACHE PERFORMANCE METRICS:")
                progress_callback(f"  * Cache Backend Status        : Enabled ({backend_str})")
                progress_callback(f"  * Total Cache Reads           : {cache_metrics['total_reads']}")
                progress_callback(f"  * Total Cache Hits (Served 0ms): {cache_metrics['hits']} ({cache_metrics['hit_percentage']}%)")
                progress_callback(f"    |-- Tier-1 Aggregated Hits   : {t1_hits}")
                progress_callback(f"    +-- Tier-2 Individual Hits   : {t2_hits}")
                progress_callback(f"  * Cache Misses (API Calls)    : {cache_metrics['misses']} ({cache_metrics['miss_percentage']}%)")
                progress_callback(f"  * Total Cache Writes / Updates: {cache_metrics['writes']}")

                evaluated_keys = []
                for idx, q_slices in enumerate(queries, 1):
                    ck, _ = self._build_cache_key(slices=q_slices, passengers=passengers, cabin_class=cabin_class)
                    evaluated_keys.append(ck)
                    size_bytes = self.cache.get_key_size_bytes(ck) if self.cache else 0
                    size_str = f"{size_bytes / (1024 * 1024):.2f} MB ({size_bytes / 1024:.1f} KB)" if size_bytes >= 1024 * 1024 else f"{size_bytes / 1024:.1f} KB"
                    progress_callback(f"  * Cache Key [{idx}/{total_queries}]               : {ck} (Payload Size: {size_str})")

                progress_callback(f"  * Read Latency (Min/Max/Avg)  : {cache_metrics['read_min_ms']:.2f}ms / {cache_metrics['read_max_ms']:.2f}ms / {cache_metrics['read_avg_ms']:.2f}ms")
                progress_callback(f"  * Write Latency (Min/Max/Avg) : {cache_metrics['write_min_ms']:.2f}ms / {cache_metrics['write_max_ms']:.2f}ms / {cache_metrics['write_avg_ms']:.2f}ms")
                progress_callback(f"  * Cache TTL                   : {cache_metrics['ttl_seconds']} seconds (1 hour)")
            progress_callback("=" * 65)

        max_offers = getattr(self.client.config, "max_cached_offers", 40)
        max_non_stop = getattr(self.client.config, "max_non_stop_offers", 10)

        unique_offers.sort(key=lambda o: float(getattr(o, "total_amount", 0.0) or 0.0))
        non_stop_unique = [o for o in unique_offers if self._is_non_stop(o)]
        non_stop_unique.sort(key=lambda o: float(getattr(o, "total_amount", 0.0) or 0.0))
        top_non_stop = non_stop_unique[:max_non_stop]

        combined_unique = list(unique_offers[:max_offers])
        existing_ids = set(getattr(o, "id", "") for o in combined_unique)
        for ns in top_non_stop:
            ns_id = getattr(ns, "id", "")
            if ns_id and ns_id not in existing_ids:
                combined_unique.append(ns)
                existing_ids.add(ns_id)

        combined_unique.sort(key=lambda o: float(getattr(o, "total_amount", 0.0) or 0.0))

        combined_airline_highlights = self.compute_all_airline_highlights(all_offers)
        highlights = self.compute_category_highlights(combined_unique, all_airline_highlights=combined_airline_highlights)

        non_stop_summaries = [self._build_offer_summary(o) for o in top_non_stop if o]
        non_stop_summaries = [s for s in non_stop_summaries if s is not None]
        shortest_non_stop_summaries = sorted(non_stop_summaries, key=lambda s: s.get("duration_minutes") or 99999)

        output_json = {
            "category_highlights": highlights,
            "airline_highlights": combined_airline_highlights,
            "cheapest_non_stop_offers": non_stop_summaries,
            "shortest_non_stop_offers": shortest_non_stop_summaries,
            "top_offers": [self._build_offer_summary(o) for o in combined_unique if o]
        }

        def _to_raw(obj):
            if isinstance(obj, dict):
                return obj
            if hasattr(obj, "__dataclass_fields__"):
                from dataclasses import asdict
                return asdict(obj)
            if hasattr(obj, "to_dict"):
                return obj.to_dict()
            return getattr(obj, "__dict__", str(obj))

        # 2. Save aggregated multi-day search result into Tier-1 Redis Cache Key
        if self.cache and self.cache.enabled and combined_unique:
            cached_offers_raw = [_to_raw(o) for o in combined_unique]
            cached_non_stop_raw = [_to_raw(o) for o in top_non_stop]
            opt_data_to_cache = {
                "offers": cached_offers_raw,
                "non_stop_offers": cached_non_stop_raw,
                "category_highlights": highlights,
                "airline_highlights": combined_airline_highlights,
                "output_json": output_json
            }
            self.cache.set(opt_cache_key, opt_data_to_cache)

        res_list = OfferList(combined_unique, category_highlights=highlights)
        setattr(res_list, "airline_highlights", combined_airline_highlights)
        setattr(res_list, "non_stop_offers", top_non_stop)
        setattr(res_list, "output_json", output_json)
        setattr(res_list, "opt_cache_key", opt_cache_key)
        return res_list
