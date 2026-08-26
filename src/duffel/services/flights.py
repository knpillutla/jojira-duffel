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

    def _parse_dt_parts(self, dt_val: Optional[str]) -> tuple[str, str, str]:
        """Given ISO datetime string like '2026-10-01T17:40:00Z', return (iso_str, date_str, time_str)."""
        if not dt_val or not isinstance(dt_val, str):
            return "", "", ""
        clean_dt = dt_val.strip()
        if "T" in clean_dt:
            parts = clean_dt.split("T", 1)
            d_part = parts[0]
            t_part = parts[1].replace("Z", "").split("+")[0].split("-")[0]
            return clean_dt, d_part, t_part
        return clean_dt, clean_dt, ""

    def _build_offer_summary(self, offer: Any) -> Optional[dict[str, Any]]:
        """Construct a standardized summary dict for a flight offer."""
        if not offer:
            return None

        if isinstance(offer, dict):
            if offer.get("is_external_web_fare") or "price" in offer or "offer_id" in offer:
                return offer
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
        stop_names: list[str] = []
        leg_codes: list[str] = []
        departure_at = ""
        departure_date = ""
        departure_time = ""
        arrival_at = ""
        arrival_date = ""
        arrival_time = ""
        return_departure_at = ""
        return_departure_date = ""
        return_departure_time = ""
        return_arrival_at = ""
        return_arrival_date = ""
        return_arrival_time = ""
        slices_detail: list[dict[str, Any]] = []

        origin_name = ""
        origin_code = ""
        destination_name = ""
        destination_code = ""
        city_by_code = {
            "ATL": "Atlanta",
            "OSL": "Oslo",
            "LHR": "London",
            "JFK": "New York",
            "CDG": "Paris",
            "KEF": "Reykjavik",
        }

        def location_name(location: Any, code: str) -> str:
            if isinstance(location, dict):
                return str(
                    location.get("city_name")
                    or location.get("city")
                    or city_by_code.get(code)
                    or location.get("name")
                    or code
                )
            return city_by_code.get(code) or str(location or code)

        for slice_index, slc in enumerate(slices):
            if isinstance(slc, dict):
                segs = slc.get("segments", [])
                dur_str = slc.get("duration", "")
                slice_origin = slc.get("origin", {})
                slice_destination = slc.get("destination", {})
            else:
                segs = getattr(slc, "segments", [])
                dur_str = getattr(slc, "duration", "")
                slice_origin = getattr(slc, "origin", {})
                slice_destination = getattr(slc, "destination", {})

            slc_orig_code = str(slice_origin.get("iata_code") or "") if isinstance(slice_origin, dict) else str(getattr(slice_origin, "iata_code", "") or "")
            slc_dest_code = str(slice_destination.get("iata_code") or "") if isinstance(slice_destination, dict) else str(getattr(slice_destination, "iata_code", "") or "")

            if slice_index == 0:
                if isinstance(slice_origin, dict):
                    origin_code = str(slice_origin.get("iata_code") or "")
                    origin_name = location_name(slice_origin, origin_code)
                else:
                    origin_code = str(getattr(slice_origin, "iata_code", "") or "")
                    origin_name = location_name(slice_origin, origin_code)

                if isinstance(slice_destination, dict):
                    destination_code = str(slice_destination.get("iata_code") or "")
                    destination_name = location_name(slice_destination, destination_code)
                else:
                    destination_code = str(getattr(slice_destination, "iata_code", "") or "")
                    destination_name = location_name(slice_destination, destination_code)

            stops = max(0, len(segs) - 1)
            if stops > max_stops:
                max_stops = stops

            for segment in segs[:-1]:
                if isinstance(segment, dict):
                    destination = segment.get("destination", {})
                else:
                    destination = getattr(segment, "destination", {})
                if isinstance(destination, dict):
                    leg_code = destination.get("iata_code")
                else:
                    leg_code = getattr(destination, "iata_code", None)
                stop_name = location_name(destination, str(leg_code or ""))
                if stop_name:
                    stop_names.append(str(stop_name))
                if leg_code:
                    leg_codes.append(str(leg_code))

            s_dep_at = ""
            s_dep_date = ""
            s_dep_time = ""
            s_arr_at = ""
            s_arr_date = ""
            s_arr_time = ""

            if segs:
                first_segment = segs[0]
                last_segment = segs[-1]
                if isinstance(first_segment, dict):
                    raw_dep = str(first_segment.get("departing_at") or first_segment.get("departure_time") or "")
                else:
                    raw_dep = str(getattr(first_segment, "departing_at", "") or getattr(first_segment, "departure_time", "") or "")

                if isinstance(last_segment, dict):
                    raw_arr = str(last_segment.get("arriving_at") or last_segment.get("arrival_time") or "")
                else:
                    raw_arr = str(getattr(last_segment, "arriving_at", "") or getattr(last_segment, "arrival_time", "") or "")

                s_dep_at, s_dep_date, s_dep_time = self._parse_dt_parts(raw_dep)
                s_arr_at, s_arr_date, s_arr_time = self._parse_dt_parts(raw_arr)

                if slice_index == 0:
                    departure_at, departure_date, departure_time = s_dep_at, s_dep_date, s_dep_time
                    arrival_at, arrival_date, arrival_time = s_arr_at, s_arr_date, s_arr_time
                elif slice_index == 1:
                    return_departure_at, return_departure_date, return_departure_time = s_dep_at, s_dep_date, s_dep_time
                    return_arrival_at, return_arrival_date, return_arrival_time = s_arr_at, s_arr_date, s_arr_time

            slice_dur_min = 0
            if dur_str and isinstance(dur_str, str):
                import re
                h_match = re.search(r"(\d+)H", dur_str)
                m_match = re.search(r"(\d+)M", dur_str)
                hours = int(h_match.group(1)) if h_match else 0
                mins = int(m_match.group(1)) if m_match else 0
                slice_dur_min = hours * 60 + mins
                if slice_dur_min > 0:
                    total_dur_min += slice_dur_min

            s_dur_str = f"{slice_dur_min // 60}h {slice_dur_min % 60}m" if slice_dur_min > 0 else dur_str

            slices_detail.append({
                "slice_index": slice_index,
                "type": "outbound" if slice_index == 0 else ("return" if slice_index == 1 else f"slice_{slice_index}"),
                "origin_code": slc_orig_code,
                "destination_code": slc_dest_code,
                "departure_at": s_dep_at,
                "departure_date": s_dep_date,
                "departure_time": s_dep_time,
                "arrival_at": s_arr_at,
                "arrival_date": s_arr_date,
                "arrival_time": s_arr_time,
                "duration": s_dur_str,
                "stops": stops,
            })

        dur_str_formatted = "N/A"
        if total_dur_min > 0:
            h = total_dur_min // 60
            m = total_dur_min % 60
            dur_str_formatted = f"{h}h {m}m" if (h > 0 and m > 0) else (f"{h}h" if h > 0 else f"{m}m")

        stop_type = "Non-stop" if max_stops == 0 else (f"{max_stops}-Stop" if max_stops == 1 else f"{max_stops}-Stops")

        payment_req = getattr(offer, "payment_requirements", {}) if hasattr(offer, "payment_requirements") else (offer.get("payment_requirements", {}) if isinstance(offer, dict) else {})
        if not isinstance(payment_req, dict):
            payment_req = {}

        requires_instant = bool(payment_req.get("requires_instant_payment", False))
        payment_required_by = payment_req.get("payment_required_by")

        res: dict[str, Any] = {
            "offer_id": o_id,
            "price": f"{curr} {amt}",
            "total_amount": float(amt or 0.0),
            "currency": curr,
            "airline": owner or "Airline",
            "origin": f"{origin_name} ({origin_code})" if origin_code else origin_name,
            "origin_name": origin_name or origin_code,
            "origin_code": origin_code,
            "destination": f"{destination_name} ({destination_code})" if destination_code else destination_name,
            "destination_name": destination_name or destination_code,
            "destination_code": destination_code,
            "max_stops": max_stops,
            "legs": stop_type,
            "leg_names": ", ".join(stop_names),
            "leg_codes": ", ".join(leg_codes),
            "duration": dur_str_formatted,
            "duration_minutes": total_dur_min if total_dur_min > 0 else None,
            "duration_hours": round(total_dur_min / 60, 2) if total_dur_min > 0 else None,
            "departure_at": departure_at,
            "departure_date": departure_date,
            "departure_time": departure_time,
            "arrival_at": arrival_at,
            "arrival_date": arrival_date,
            "arrival_time": arrival_time,
            "payment_requirements": payment_req,
            "requires_instant_payment": requires_instant,
            "payment_required_by": payment_required_by,
            "slice_details": slices_detail,
        }
        if len(slices) > 1:
            res["return_departure_at"] = return_departure_at
            res["return_departure_date"] = return_departure_date
            res["return_departure_time"] = return_departure_time
            res["return_arrival_at"] = return_arrival_at
            res["return_arrival_date"] = return_arrival_date
            res["return_arrival_time"] = return_arrival_time

        return res

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

        # Search web scrapers for direct web fares (e.g. Frontier, Spirit) if available
        try:
            from .scrapers import ScraperRegistry
            registry = ScraperRegistry(enabled=True)
            if summaries:
                s0 = summaries[0]
                scraped_fares = registry.search_all_scrapers(
                    origin=s0.get("origin_code", "ATL"),
                    destination=s0.get("destination_code", "MCO"),
                    departure_date=s0.get("departure_date", ""),
                    return_date=s0.get("return_date"),
                )
                for sf in scraped_fares:
                    summaries.append(sf)
        except Exception:
            pass

        summaries.sort(key=lambda s: s["total_amount"])

        cheapest_all = summaries[0]

        non_stops = [s for s in summaries if s.get("max_stops", 0) == 0 or s.get("is_non_stop", False)]
        cheapest_non_stop = non_stops[0] if non_stops else None
        non_stops_dur = [s for s in non_stops if s.get("duration_minutes") is not None]
        shortest_non_stop = min(non_stops_dur, key=lambda s: s["duration_minutes"]) if non_stops_dur else cheapest_non_stop

        one_stops = [s for s in summaries if s.get("max_stops") == 1]
        cheapest_1stop = one_stops[0] if one_stops else None

        two_stops = [s for s in summaries if s.get("max_stops", 0) >= 2]
        cheapest_2stop = two_stops[0] if two_stops else None

        with_dur = [s for s in summaries if s.get("duration_minutes") is not None]
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
            # Premium Enterprise Keys
            "lowest_fare_deal": cheapest_all,
            "lowest_direct_flight": cheapest_non_stop,
            "fastest_express_flight": shortest_non_stop,
            "lowest_1_connection": cheapest_1stop,
            "lowest_2_connection": cheapest_2stop,
            "preferred_airline_lowest": {
                "favorite_airline": fav_airline_display,
                "offer": cheapest_fav
            },
            "preferred_airline_fastest": {
                "favorite_airline": fav_airline_display,
                "offer": shortest_fav
            },
            # Backward-Compatible Aliases
            "overall_lowest": cheapest_all,
            "overall_cheapest": cheapest_all,
            "lowest_non_stop": cheapest_non_stop,
            "cheapest_non_stop": cheapest_non_stop,
            "shortest_non_stop": shortest_non_stop,
            "lowest_1_stop": cheapest_1stop,
            "lowest_2_stop": cheapest_2stop,
            "shortest_flight": shortest_flight,
            "favorite_airline_lowest": {
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

    def _calculate_earliest_ttl(self, offers: list, default_ttl: Optional[int] = None) -> int:
        """
        Calculates dynamic Redis cache TTL in seconds based on the earliest expiry date
        among all offers combined in the search response.
        """
        from datetime import datetime, timezone
        if default_ttl is None:
            default_ttl = getattr(self.client.config, "cache_ttl_seconds", 3600)

        now_utc = datetime.now(timezone.utc)
        earliest_expiry: Optional[datetime] = None

        for o in offers:
            if not o:
                continue
            if isinstance(o, dict):
                exp_str = o.get("expires_at") or (o.get("payment_requirements") or {}).get("price_guarantee_expires_at")
            else:
                exp_str = getattr(o, "expires_at", None)

            if exp_str:
                try:
                    clean_str = str(exp_str).replace("Z", "+00:00")
                    dt = datetime.fromisoformat(clean_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if earliest_expiry is None or dt < earliest_expiry:
                        earliest_expiry = dt
                except Exception:
                    pass

        if earliest_expiry is not None:
            remaining_seconds = int((earliest_expiry - now_utc).total_seconds())
            if remaining_seconds > 0:
                return min(remaining_seconds, default_ttl)
            else:
                return 1

        return default_ttl

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
                    raw_offers = cached_data.get("offers", [])
                    from datetime import datetime, timezone
                    now_iso = datetime.now(timezone.utc).isoformat()

                    # Check if ANY offer in cached response has expired
                    any_expired = False
                    for o in raw_offers:
                        if isinstance(o, dict):
                            exp = o.get("expires_at") or (o.get("payment_requirements") or {}).get("price_guarantee_expires_at")
                            if exp and str(exp) <= now_iso:
                                any_expired = True
                                break

                    if any_expired:
                        # Evict stale cache key so fresh data will be fetched live from Duffel API
                        print(f"[CACHE EVICTION] Expired offer detected in cache key '{cache_key}'. Evicting cache & re-executing search live.")
                        self.cache.delete(cache_key)
                    else:
                        valid_raw_offers = list(raw_offers)
                        valid_raw_offers.sort(key=lambda o: float(o.get("total_amount") or 0.0))
                        all_airline_highlights = cached_data.get("airline_highlights", {})
                        non_stop_cached = cached_data.get("non_stop_offers") or []
                        highlight_offers = list(valid_raw_offers)
                        highlight_ids = {o.get("id") for o in highlight_offers if isinstance(o, dict)}
                        for non_stop_offer in non_stop_cached:
                            if isinstance(non_stop_offer, dict) and non_stop_offer.get("id") not in highlight_ids:
                                highlight_offers.append(non_stop_offer)
                                highlight_ids.add(non_stop_offer.get("id"))
                        highlights = self.compute_category_highlights(
                            highlight_offers,
                            all_airline_highlights=all_airline_highlights
                        )
                        output_json = cached_data.get("output_json")
                        if isinstance(output_json, dict):
                            output_json = dict(output_json)
                            output_json["category_highlights"] = highlights
                        offers = OfferList([FlightOffer.from_dict(o) for o in valid_raw_offers[:max_offers]], category_highlights=highlights)
                        setattr(offers, "airline_highlights", all_airline_highlights)
                        if output_json:
                            setattr(offers, "output_json", output_json)
                        if non_stop_cached:
                            setattr(offers, "non_stop_offers", [FlightOffer.from_dict(o) for o in non_stop_cached])
                        return offers
                else:
                    return cached_data

        # 2. Cache MISS / Force Refresh -> execute provider adapter request
        response = self.adapter.search_flights(payload)
        data = response.get("data", {})

        req_id = data.get("id")
        if return_offers and req_id and not data.get("offers"):
            offers_res = self.adapter.list_offers(req_id, params={"sort": "total_amount", "limit": str(max_offers)})
            if isinstance(offers_res, dict) and isinstance(offers_res.get("data"), list):
                data["offers"] = offers_res["data"]

        max_offers = getattr(self.client.config, "max_cached_offers", 40)
        max_non_stop = getattr(self.client.config, "max_non_stop_offers", 10)

        # 3. Create or replace updated response value in Redis cache with dynamic TTL based on earliest expiry date
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
                    "lowest_non_stop_offers": non_stop_summaries,
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
                dynamic_ttl = self._calculate_earliest_ttl(combined_raw)
            else:
                data_to_cache = data
                dynamic_ttl = getattr(self.client.config, "cache_ttl_seconds", 3600)

            self.cache.set(cache_key, data_to_cache, ttl_seconds=dynamic_ttl)

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
        """
        res = self.adapter.get_offer_request(offer_request_id)
        return res.get("data", {})

    def list_offers(
        self,
        offer_request_id: str,
        sort: Optional[str] = None,
        max_connections: Optional[int] = None,
    ) -> list[FlightOffer]:
        """
        List offers associated with an offer request.
        """
        params: dict[str, Any] = {}
        if sort:
            params["sort"] = sort
        if max_connections is not None:
            params["max_connections"] = max_connections

        res = self.adapter.list_offers(offer_request_id, params=params)
        raw_offers = res.get("data", [])
        return [FlightOffer.from_dict(o) for o in raw_offers]

    def get_offer(self, offer_id: str) -> FlightOffer:
        """
        Retrieve a single flight offer by ID.
        """
        res = self.adapter.get_offer(offer_id)
        return FlightOffer.from_dict(res.get("data", {}))

    def tokenize_card(self, card_data: dict[str, Any]) -> str:
        """
        Tokenizes raw credit card details.
        """
        payload = {
            "name": card_data.get("name") or "John Doe",
            "number": str(card_data.get("number", "4500000000000000")).replace(" ", "").replace("-", ""),
            "exp_month": str(card_data.get("expiry_month") or card_data.get("exp_month") or "12").strip().zfill(2),
            "exp_year": str(card_data.get("expiry_year") or card_data.get("exp_year") or "2028").strip(),
            "cvc": str(card_data.get("cvc", "123")).strip(),
            "address_postcode": card_data.get("address_postcode") or card_data.get("postcode") or "EC2A 4NE"
        }
        if len(payload["exp_year"]) == 2:
            payload["exp_year"] = "20" + payload["exp_year"]

        res = self.adapter.tokenize_card(payload)
        card_id = res.get("data", {}).get("id")
        return card_id

    def create_component_client_key(self) -> dict[str, Any]:
        """
        Generate a short-lived Client Component Key.
        """
        from datetime import datetime
        res = self.adapter.create_component_client_key()
        data = res.get("data", {})
        key_val = data.get("component_client_key") or data.get("client_key") or data.get("id")
        return {
            "client_key": key_val,
            "component_client_key": key_val,
            "live_mode": True,
            "created_at": datetime.now().isoformat()
        }

    def create_three_d_secure_session(self, card_id: str, amount: str = '100.00', currency: str = 'USD', offer_id: str = None) -> dict[str, Any]:
        """
        Create a 3D Secure session via Provider Adapter.
        """
        payload: dict[str, Any] = {
            "card_id": card_id,
            "amount": str(amount) if amount else "100.00",
            "currency": currency,
        }
        if offer_id:
            payload["resource"] = offer_id

        res = self.adapter.create_three_d_secure_session(payload)
        return res.get("data", {})

    def create_order(
        self,
        selected_offers: Union[str, list[str]],
        passengers: list[Union[Passenger, dict[str, Any]]],
        payments: Optional[list[Union[Payment, dict[str, Any]]]] = None,
        type: str = "hold",
        idempotency_key: Optional[str] = None,
    ) -> FlightOrder:
        """
        Create a flight booking order with Duffel API.

        Endpoint: POST /air/orders
        """
        if isinstance(selected_offers, str):
            offer_ids = [selected_offers]
        else:
            offer_ids = list(selected_offers)

        # Fetch actual offer from Duffel API to get valid passenger IDs
        real_offer = None
        offer_passenger_ids = []
        try:
            real_offer = self.get_offer(offer_ids[0])
            if hasattr(real_offer, "passengers") and real_offer.passengers:
                for op in real_offer.passengers:
                    op_id = getattr(op, "id", None) or (op.get("id") if isinstance(op, dict) else None)
                    if op_id:
                        offer_passenger_ids.append(op_id)
        except Exception:
            pass

        formatted_passengers = []
        for i, p in enumerate(passengers):
            if isinstance(p, Passenger):
                p_dict = p.to_dict()
            elif isinstance(p, dict):
                p_dict = dict(p)
            else:
                p_dict = {}

            # Assign valid passenger ID from Duffel offer
            pid = str(p_dict.get("id") or "").strip()
            if i < len(offer_passenger_ids):
                p_dict["id"] = offer_passenger_ids[i]
            elif pid and pid.startswith("pas_"):
                p_dict["id"] = pid
            else:
                p_dict.pop("id", None)

            # Ensure title is populated as required by Duffel API
            if not p_dict.get("title"):
                gender_str = str(p_dict.get("gender") or "").lower()
                p_dict["title"] = "ms" if gender_str in ["f", "female"] else "mr"

            formatted_passengers.append(p_dict)

        payload = {
            "type": type,
            "selected_offers": offer_ids,
            "passengers": formatted_passengers,
        }

        # ONLY add payments array if order type is NOT "hold" (Strategy A hold orders omit payments on creation)
        if type != "hold":
            if not payments:
                payments = [Payment(type="balance", currency=real_offer.total_currency or "USD", amount=real_offer.total_amount)]

            formatted_payments = []
            for pym in payments:
                if isinstance(pym, Payment):
                    pym_dict = pym.to_dict()
                elif isinstance(pym, dict):
                    pym_dict = dict(pym)
                else:
                    pym_dict = {"type": "balance"}

                # Automatically match the exact offer total_amount and currency required by Duffel API
                if hasattr(real_offer, "total_amount") and real_offer.total_amount:
                    pym_dict["amount"] = str(real_offer.total_amount)
                    pym_dict["currency"] = str(real_offer.total_currency or "USD")

                # Ensure card_id is present if passed in card_id or aliases
                c_id = pym_dict.get("card_id") or pym_dict.get("id") or pym_dict.get("card_token") or pym_dict.get("token")
                if c_id:
                    pym_dict["card_id"] = str(c_id).strip()

                # Pass three_d_secure_session_id if explicitly provided
                tds = (
                    pym_dict.get("three_d_secure_session_id")
                    or pym_dict.get("card_session_id")
                    or pym_dict.get("session_id")
                    or pym_dict.get("three_d_session_id")
                    or pym_dict.get("tds_session_id")
                )
                if tds:
                    pym_dict["three_d_secure_session_id"] = str(tds).strip()

                formatted_payments.append(pym_dict)

            payload["payments"] = formatted_payments

        res = self.adapter.create_flight_order(payload)
        return FlightOrder.from_dict(res.get("data", {}))

    def pay_order(
        self,
        order_id: str,
        payment: Optional[Union[Payment, dict[str, Any]]] = None,
        amount: Optional[str] = None,
        currency: Optional[str] = None,
        payment_type: str = "balance",
    ) -> dict[str, Any]:
        """
        Create a payment for a hold order to ticket/confirm seats (Strategy A Step 2).

        Endpoint: POST /air/orders/{order_id}/payments
        """
        if isinstance(payment, Payment):
            pym_dict = payment.to_dict()
        elif isinstance(payment, dict):
            pym_dict = dict(payment)
        else:
            pym_dict = {}

        if "type" not in pym_dict:
            pym_dict["type"] = payment_type
        if amount and "amount" not in pym_dict:
            pym_dict["amount"] = str(amount)
        if currency and "currency" not in pym_dict:
            pym_dict["currency"] = str(currency)

        # If amount/currency missing, fetch hold order details automatically
        if "amount" not in pym_dict or "currency" not in pym_dict:
            order_info = self.get_order(order_id)
            if "amount" not in pym_dict:
                pym_dict["amount"] = str(getattr(order_info, "total_amount", "0.00"))
            if "currency" not in pym_dict:
                pym_dict["currency"] = str(getattr(order_info, "total_currency", "USD"))

        res = self.adapter.pay_flight_order(order_id, pym_dict)
        return res.get("data", {})

    def get_order(self, order_id: str) -> FlightOrder:
        """
        Retrieve order details.
        """
        res = self.adapter.get_flight_order(order_id)
        return FlightOrder.from_dict(res.get("data", {}))

    def list_orders(self, limit: int = 50) -> list[FlightOrder]:
        """
        List booked flight orders.
        """
        res = self.adapter.list_flight_orders(limit=limit)
        raw_orders = res.get("data", [])
        return [FlightOrder.from_dict(o) for o in raw_orders]

    def cancel_order(self, order_id: str) -> FlightCancellation:
        """
        Cancel a booked order.
        """
        payload = {"order_id": order_id}
        res = self.adapter.cancel_flight_order(payload)
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

    def search_exact(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passengers: Optional[list[Union[Passenger, dict[str, Any]]]] = None,
        cabin_class: Union[CabinClass, str] = CabinClass.ECONOMY,
        force_refresh: bool = False,
        progress_callback: Optional[Any] = None,
    ) -> list[FlightOffer]:
        """
        Execute standard exact-date flight search for specific departure_date and optional return_date.
        Calculates trip duration automatically if return_date is provided and calls search_optimized
        with flex_days=0 and min_duration_days == max_duration_days.
        """
        from datetime import datetime
        min_dur = 7
        max_dur = 7
        if return_date and return_date.strip():
            try:
                d1 = datetime.strptime(departure_date, "%Y-%m-%d")
                d2 = datetime.strptime(return_date.strip(), "%Y-%m-%d")
                dur = max(1, (d2 - d1).days)
                min_dur = dur
                max_dur = dur
            except Exception:
                pass

        return self.search_optimized(
            origin=origin,
            destination=destination,
            target_date=departure_date,
            target_return_date=return_date.strip() if (return_date and return_date.strip()) else None,
            min_duration_days=min_dur,
            max_duration_days=max_dur,
            flex_days=0,
            passengers=passengers,
            cabin_class=cabin_class,
            force_refresh=force_refresh,
            progress_callback=progress_callback,
        )

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

                # Check if ANY offer in cached response has expired
                any_expired = False
                for o in raw_offers:
                    if isinstance(o, dict):
                        exp = o.get("expires_at") or (o.get("payment_requirements") or {}).get("price_guarantee_expires_at")
                        if exp and str(exp) <= now_iso:
                            any_expired = True
                            break

                if any_expired:
                    # Evict Tier-1 cache so a fresh search is executed live against Duffel API
                    print(f"[TIER-1 CACHE EVICTION] Expired offer detected in aggregated key '{opt_cache_key}'. Evicting cache & re-executing search live.")
                    self.cache.delete(opt_cache_key)
                else:
                    valid_raw_offers = list(raw_offers)
                    max_offers = getattr(self.client.config, "max_cached_offers", 40)
                    all_airline_highlights = cached_opt.get("airline_highlights", {})
                    non_stop_cached = cached_opt.get("non_stop_offers") or []
                    highlight_offers = list(valid_raw_offers)
                    highlight_ids = {o.get("id") for o in highlight_offers if isinstance(o, dict)}
                    for non_stop_offer in non_stop_cached:
                        if isinstance(non_stop_offer, dict) and non_stop_offer.get("id") not in highlight_ids:
                            highlight_offers.append(non_stop_offer)
                            highlight_ids.add(non_stop_offer.get("id"))
                    highlights = self.compute_category_highlights(
                        highlight_offers, all_airline_highlights=all_airline_highlights
                    )
                    output_json = cached_opt.get("output_json")
                    if isinstance(output_json, dict):
                        output_json = dict(output_json)
                        output_json["category_highlights"] = highlights
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

        # Query Web Scraper Engine (e.g. Frontier, Spirit direct web fares)
        try:
            from .scrapers import ScraperRegistry
            registry = ScraperRegistry(enabled=True)
            scraped_fares = registry.search_all_scrapers(
                origin=origin,
                destination=destination,
                departure_date=target_date,
                return_date=target_return_date,
            )
            if scraped_fares:
                for sf in scraped_fares:
                    all_offers.append(sf)
        except Exception as sc_err:
            print(f"[!] Web Scraper Engine notice: {sc_err}")

        # Deduplicate and sort all offers by total price ascending
        seen_ids = set()
        unique_offers = []
        for o in all_offers:
            if isinstance(o, dict):
                o_id = o.get("id") or o.get("offer_id")
            else:
                o_id = getattr(o, "id", None)
            if o_id and o_id not in seen_ids:
                seen_ids.add(o_id)
                unique_offers.append(o)
            elif not o_id:
                unique_offers.append(o)

        def get_offer_amount(o):
            if isinstance(o, dict):
                return float(o.get("total_amount", 0.0) or 0.0)
            return float(getattr(o, "total_amount", 0.0) or 0.0)

        unique_offers.sort(key=get_offer_amount)

        # Metrics summary
        total_wall_sec = time.perf_counter() - search_start_time
        metrics = self.client.get_metrics_summary()
        cache_metrics = self.cache.get_metrics_summary() if self.cache else {}

        if unique_offers:
            u0 = unique_offers[0]
            if isinstance(u0, dict):
                c_val = u0.get("currency") or u0.get("total_currency", "USD")
                a_val = u0.get("total_amount", "0.00")
            else:
                c_val = getattr(u0, "total_currency", "USD")
                a_val = getattr(u0, "total_amount", "0.00")
            best_price_str = f"{c_val} {a_val}"
        else:
            best_price_str = "N/A"
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
            "lowest_price": best_price_str,
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

        unique_offers.sort(key=get_offer_amount)
        non_stop_unique = [o for o in unique_offers if self._is_non_stop(o)]
        non_stop_unique.sort(key=get_offer_amount)
        top_non_stop = non_stop_unique[:max_non_stop]

        combined_unique = list(unique_offers[:max_offers])
        def get_o_id(o):
            if isinstance(o, dict):
                return o.get("id") or o.get("offer_id") or ""
            return getattr(o, "id", "") or ""

        existing_ids = set(get_o_id(o) for o in combined_unique if get_o_id(o))
        for ns in top_non_stop:
            ns_id = get_o_id(ns)
            if ns_id and ns_id not in existing_ids:
                combined_unique.append(ns)
                existing_ids.add(ns_id)

        combined_unique.sort(key=get_offer_amount)

        combined_airline_highlights = self.compute_all_airline_highlights(all_offers)
        highlights = self.compute_category_highlights(combined_unique, all_airline_highlights=combined_airline_highlights)

        non_stop_summaries = [self._build_offer_summary(o) for o in top_non_stop if o]
        non_stop_summaries = [s for s in non_stop_summaries if s is not None]
        shortest_non_stop_summaries = sorted(non_stop_summaries, key=lambda s: s.get("duration_minutes") or 99999)

        output_json = {
            "category_highlights": highlights,
            "airline_highlights": combined_airline_highlights,
            "lowest_non_stop_offers": non_stop_summaries,
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
            # Record-Level Redis Caching for individual flight offers
            self.cache.set_records_batch("flights", cached_offers_raw, id_key="id")
            dynamic_ttl = self._calculate_earliest_ttl(cached_offers_raw)
            self.cache.set(opt_cache_key, opt_data_to_cache, ttl_seconds=dynamic_ttl)

        res_list = OfferList(combined_unique, category_highlights=highlights)
        setattr(res_list, "airline_highlights", combined_airline_highlights)
        setattr(res_list, "non_stop_offers", top_non_stop)
        setattr(res_list, "output_json", output_json)
        setattr(res_list, "opt_cache_key", opt_cache_key)
        return res_list
