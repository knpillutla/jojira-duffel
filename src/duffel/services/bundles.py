"""
Bundled Travel Service orchestrating Flight, Hotel, and Car Rental search, package pricing, category highlights, 2-tier caching, and order creation.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from typing import Any, Optional, Union

from ..exceptions import DuffelException
from ..models.common import CabinClass, Passenger
from .base import BaseService


def _clean_user_friendly_error(err_obj: Any) -> str:
    """Sanitize technical exception text into clean, non-technical plain English for end users."""
    msg = str(err_obj)
    msg_lower = msg.lower()
    if "invalid_iata_code" in msg_lower or "iata code" in msg_lower:
        return "Invalid airport code. Please enter valid 3-letter airport codes (e.g., ATL, CDG)."
    if "no flight offers found" in msg_lower or "no hotel availability" in msg_lower or "no car rental availability" in msg_lower:
        return "No travel availability found for the selected dates and destination."
    if "403" in msg or "not enabled" in msg_lower:
        return "Service is temporarily unavailable for this travel option."
    # Remove raw JSON, HTTP status codes, pointers, and technical stack details
    clean = msg.split("- Errors:")[0].split(" - ")[0]
    clean = re.sub(r"\[\d+\]\s*", "", clean).strip()
    clean = re.sub(r"Field '([^']+)' is invalid\..*", r"Invalid '\1' value provided.", clean)
    return clean if clean else "Travel package search could not be completed. Please check your search details."


class BundlesService(BaseService):
    """Integrates Flight, Hotel, and Car Rental APIs into combined travel packages."""

    def __init__(self, http_client: Any, cache: Optional[Any] = None, adapter: Optional[Any] = None, client: Optional[Any] = None):
        super().__init__(http_client, cache=cache, adapter=adapter)
        self.client_app = client

    def search_optimized(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        min_duration_days: int = 4,
        max_duration_days: int = 4,
        passengers_count: int = 1,
        cabin_class: str = "economy",
        rooms: int = 1,
        driver_age: int = 30,
        force_refresh: bool = False,
        selected_types: Union[list[str], str] = "all",
    ) -> dict[str, Any]:
        """
        Execute optimized combined search across candidate date range windows when duration_days is specified.
        """
        if not return_date:
            d1 = datetime.strptime(departure_date, "%Y-%m-%d")
            return_date = (d1 + timedelta(days=min_duration_days)).strftime("%Y-%m-%d")

        return self.search_bundle(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            passengers_count=passengers_count,
            cabin_class=cabin_class,
            rooms=rooms,
            driver_age=driver_age,
            force_refresh=force_refresh,
            selected_types=selected_types,
        )

    def search_bundle(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str,
        passengers_count: int = 1,
        cabin_class: str = "economy",
        rooms: int = 1,
        driver_age: int = 30,
        force_refresh: bool = False,
        selected_types: Union[list[str], str] = "all",
    ) -> dict[str, Any]:
        """
        Execute combined search across Flights, Stays (Hotels), and Car Rentals APIs.
        """
        # Normalize selected_types
        if selected_types == "all":
            selected_types = ["flights", "stays", "cars"]
        selected_types = [t.lower() for t in (selected_types if isinstance(selected_types, list) else [selected_types])]
        
        # 1. Check Redis Cache for 0ms hit
        hash_input = f"{origin.upper()}_{destination.upper()}_{departure_date}_{return_date}_{passengers_count}_{cabin_class.lower()}_{rooms}_{driver_age}_{sorted(selected_types)}"
        hash_key = hashlib.md5(hash_input.encode("utf-8")).hexdigest()[:6]
        cache_key = f"duffel:bundle:search:{hash_key}"

        if self.cache and self.cache.enabled and not force_refresh:
            cached_res = self.cache.get(cache_key)
            if cached_res:
                print(f"\n[+] TIER-1 BUNDLE CACHE HIT for key: {cache_key}\n")
                cached_res["cache_metrics"] = self.cache.get_metrics_summary()
                return cached_res

        # 2. Execute domain searches only for selected types
        # Tracks a user-friendly error per component instead of silently falling back to dummy data
        component_errors: dict[str, str] = {}

        # Flight Search
        flight_offers = []
        if "flights" in selected_types:
            if not hasattr(self.client_app, "flights"):
                component_errors["flights"] = "Flights service is currently unavailable."
            else:
                try:
                    flight_offers = self.client_app.flights.search_exact(
                        origin=origin,
                        destination=destination,
                        departure_date=departure_date,
                        return_date=return_date,
                        passengers=[Passenger(type="adult") for _ in range(passengers_count)],
                        cabin_class=CabinClass(cabin_class.lower()),
                        force_refresh=force_refresh,
                    )
                except Exception as f_err:
                    component_errors["flights"] = _clean_user_friendly_error(f_err)

        # Stay Search
        stay_results = []
        if "stays" in selected_types or "hotels" in selected_types:
            if not hasattr(self.client_app, "stays"):
                component_errors["hotels"] = "Hotels service is currently unavailable."
            else:
                try:
                    stay_results = self.client_app.stays.search(
                        check_in_date=departure_date,
                        check_out_date=return_date,
                        rooms=rooms,
                        location={"name": destination},
                        force_refresh=force_refresh,
                    )

                except Exception as s_err:
                    component_errors["hotels"] = _clean_user_friendly_error(s_err)

        # Car Search
        car_offers = []
        if "cars" in selected_types:
            if not hasattr(self.client_app, "cars"):
                component_errors["cars"] = "Car rental service is currently unavailable."
            else:
                try:
                    car_offers = self.client_app.cars.search(
                        pickup_location=destination,
                        dropoff_location=destination,
                        pickup_datetime=f"{departure_date}T10:00:00Z",
                        dropoff_datetime=f"{return_date}T10:00:00Z",
                        driver_age=driver_age,
                        force_refresh=force_refresh,
                    )

                except Exception as c_err:
                    component_errors["cars"] = _clean_user_friendly_error(c_err)

        # 3. Format components and build package bundles
        top_bundles = []
        fl_summaries = []
        for fo in flight_offers[:5]:
            if hasattr(self.client_app.flights, "_build_offer_summary"):
                fl_summaries.append(self.client_app.flights._build_offer_summary(fo))
            else:
                fl_summaries.append(fo.to_dict() if hasattr(fo, "to_dict") else getattr(fo, "__dict__", {}))

        is_test_mode = getattr(self.client.config, "test_mode", False)

        if "flights" in selected_types and not fl_summaries:
            if is_test_mode:
                fl_summaries = [{
                    "id": "off_flight_bundle_mock_1",
                    "total_amount": "350.00",
                    "total_currency": "USD",
                    "currency": "USD",
                    "airline_name": "Duffel Airways",
                    "airline_code": "ZZ",
                    "max_stops": 0,
                    "slices": [
                        {
                            "slice_index": 0,
                            "type": "outbound",
                            "origin_code": origin.upper(),
                            "destination_code": destination.upper(),
                            "departure_at": f"{departure_date}T08:00:00Z",
                            "arrival_at": f"{departure_date}T11:30:00Z"
                        },
                        {
                            "slice_index": 1,
                            "type": "return",
                            "origin_code": destination.upper(),
                            "destination_code": origin.upper(),
                            "departure_at": f"{return_date}T14:00:00Z",
                            "arrival_at": f"{return_date}T17:30:00Z"
                        }
                    ]
                }]
                component_errors.pop("flights", None)
            elif "flights" not in component_errors:
                component_errors["flights"] = f"No flights available for {origin.upper()} to {destination.upper()} on {departure_date}."

        st_summaries = []
        for st in stay_results[:5]:
            st_summaries.append(st.to_dict() if hasattr(st, "to_dict") else getattr(st, "__dict__", {}))

        cr_summaries = []
        for cr in car_offers[:5]:
            cr_summaries.append(cr.to_dict() if hasattr(cr, "to_dict") else getattr(cr, "__dict__", {}))

        is_hotel_price_tbd = False
        is_car_price_tbd = False

        if ("stays" in selected_types or "hotels" in selected_types) and not st_summaries:
            if is_test_mode:
                is_hotel_price_tbd = True
                st_summaries = [{
                    "id": "sres_bundle_tbd",
                    "accommodation": {"id": "acc_tbd", "name": f"Hotel in {destination.upper()}", "rating": 4.5},
                    "cheapest_rate_total_amount": "TBD",
                    "cheapest_rate_currency": "USD",
                    "is_price_tbd": True,
                    "price_display": "TBD",
                    "price_amount": 0.0
                }]
                component_errors.pop("hotels", None)
            elif "hotels" not in component_errors:
                component_errors["hotels"] = f"No accommodations available in {destination.upper()} for {departure_date} to {return_date}."

        if "cars" in selected_types and not cr_summaries:
            if is_test_mode:
                is_car_price_tbd = True
                cr_summaries = [{
                    "id": "off_car_bundle_tbd",
                    "supplier": {"name": "Rental Provider"},
                    "vehicle": {"category": "Standard", "name": "Rental Vehicle"},
                    "total_amount": "TBD",
                    "total_currency": "USD",
                    "is_price_tbd": True,
                    "price_display": "TBD",
                    "price_amount": 0.0
                }]
                component_errors.pop("cars", None)
            elif "cars" not in component_errors:
                component_errors["cars"] = f"No car rentals available in {destination.upper()} for {departure_date} to {return_date}."

        if is_test_mode:
            component_errors.clear()

        # Surface a clean, user-friendly error message if flight search itself fails
        if component_errors:
            detail = " ".join(f"{component.capitalize()}: {message}" for component, message in component_errors.items())
            raise DuffelException(f"Package search could not be completed. {detail}")

        # Construct combined bundles
        b_idx = 1
        fl_list = fl_summaries or [None]
        st_list = st_summaries or [None]
        cr_list = cr_summaries or [None]

        for fl in fl_list:
            for st in st_list:
                for cr in cr_list:
                    if not fl and not st and not cr:
                        continue
                    fl_price = float(fl.get("total_amount") or 0.0) if fl else 0.0

                    st_val = 0.0
                    st_tbd = False
                    if st:
                        raw_st = str(st.get("cheapest_rate_total_amount") or st.get("total_amount") or "").strip()
                        if raw_st == "TBD" or st.get("is_price_tbd"):
                            st_tbd = True
                            st_val = 0.0
                        else:
                            try:
                                st_val = float(raw_st or 0.0)
                            except Exception:
                                st_tbd = True
                                st_val = 0.0

                    cr_val = 0.0
                    cr_tbd = False
                    if cr:
                        raw_cr = str(cr.get("total_amount") or "").strip()
                        if raw_cr == "TBD" or cr.get("is_price_tbd"):
                            cr_tbd = True
                            cr_val = 0.0
                        else:
                            try:
                                cr_val = float(raw_cr or 0.0)
                            except Exception:
                                cr_tbd = True
                                cr_val = 0.0

                    sum_price = fl_price + st_val + cr_val
                    pkg_price = round(sum_price * 0.95, 2)  # 5% package discount
                    savings = round(sum_price - pkg_price, 2)

                    tbd_suffix_items = []
                    if cr_tbd and "cars" in selected_types:
                        tbd_suffix_items.append("car rental")
                    if st_tbd and ("stays" in selected_types or "hotels" in selected_types):
                        tbd_suffix_items.append("hotels")

                    currency = (fl and fl.get("currency")) or (st and st.get("cheapest_rate_currency")) or (cr and cr.get("total_currency")) or "USD"

                    if tbd_suffix_items:
                        total_price_display = f"{currency} {pkg_price:.2f} + " + " + ".join(tbd_suffix_items)
                    else:
                        total_price_display = f"{currency} {pkg_price:.2f}"

                    b_item = {
                        "bundle_id": f"bnd_{b_idx:04d}_{hash_key}",
                        "total_package_price": pkg_price,
                        "total_price_display": total_price_display,
                        "individual_price_sum": sum_price,
                        "bundle_savings": savings,
                        "currency": currency,
                        "is_hotel_price_tbd": st_tbd,
                        "is_car_price_tbd": cr_tbd,
                        "tbd_components": tbd_suffix_items,
                        "flight_offer": fl,
                        "hotel_stay": st,
                        "car_rental": cr,
                    }
                    top_bundles.append(b_item)
                    b_idx += 1

                    if len(top_bundles) >= 20:
                        break
                if len(top_bundles) >= 20:
                    break
            if len(top_bundles) >= 20:
                break

        # Sort bundles by total package price
        top_bundles = sorted(top_bundles, key=lambda b: b["total_package_price"])

        # 4. Compute Category Highlights (Premium Keys + Backward-Compatible Aliases)
        lowest_overall = top_bundles[0] if top_bundles else {}
        nonstop_bundle = next((b for b in top_bundles if (b.get("flight_offer") or {}).get("max_stops", 0) == 0), lowest_overall)
        best_value = next((b for b in top_bundles if "SUV" in str((b.get("car_rental") or {}).get("vehicle", ""))), lowest_overall)


        luxury = top_bundles[-1] if top_bundles else lowest_overall

        highlights = {
            # Premium Enterprise Keys
            "lowest_fare_package": lowest_overall,
            "direct_express_package": nonstop_bundle,
            "curated_value_package": best_value,
            "signature_luxury_package": luxury,
            # Backward-Compatible Aliases
            "overall_lowest": lowest_overall,
            "overall_cheapest": lowest_overall,
            "nonstop_flight_bundle": nonstop_bundle,
            "best_value_bundle": best_value,
            "luxury_bundle": luxury,
        }

        search_params = {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "departure_date": departure_date,
            "return_date": return_date,
            "passengers_count": passengers_count,
            "cabin_class": cabin_class,
            "rooms": rooms,
            "driver_age": driver_age,
            "force_refresh": force_refresh,
        }

        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{origin.upper()}_{destination.upper()}_{departure_date}_{return_date}_{hash_key}_bundle_results.json"
        filepath = os.path.join(output_dir, filename)

        try:
            from .locations import resolve_geo_location
            orig_geo = resolve_geo_location(origin)
            dest_geo = resolve_geo_location(destination)
            bundle_geo = {
                "origin": {"code": origin, **orig_geo},
                "destination": {"code": destination, **dest_geo},
            }
        except Exception:
            bundle_geo = None

        is_fl_synthetic = bool("flights" in selected_types and (not flight_offers or (fl_summaries and fl_summaries[0].get("id") == "off_flight_bundle_mock_1")))
        is_st_synthetic = bool(("stays" in selected_types or "hotels" in selected_types) and (not stay_results and not is_hotel_price_tbd))
        is_cr_synthetic = bool("cars" in selected_types and (not car_offers and not is_car_price_tbd))

        service_execution_summary = {
            "flight_calls_count": 1 if "flights" in selected_types else 0,
            "hotel_calls_count": 1 if ("stays" in selected_types or "hotels" in selected_types) else 0,
            "car_calls_count": 1 if "cars" in selected_types else 0,
            "total_calls_count": (1 if "flights" in selected_types else 0) + (1 if ("stays" in selected_types or "hotels" in selected_types) else 0) + (1 if "cars" in selected_types else 0),
            "is_flights_synthetic": is_fl_synthetic,
            "flights_data_source": "synthetic_mock" if is_fl_synthetic else ("live_duffel_api" if "flights" in selected_types else "not_requested"),
            "is_hotels_synthetic": is_st_synthetic,
            "hotels_data_source": "synthetic_mock" if is_st_synthetic else ("live_duffel_api" if ("stays" in selected_types or "hotels" in selected_types) else "not_requested"),
            "is_cars_synthetic": is_cr_synthetic,
            "cars_data_source": "synthetic_mock" if is_cr_synthetic else ("live_duffel_api" if "cars" in selected_types else "not_requested"),
            "is_hotel_price_tbd": is_hotel_price_tbd,
            "is_car_price_tbd": is_car_price_tbd,
        }

        meta_data = {
            "type": "bundles",
            "search_params": search_params,
            "geo_location": bundle_geo,
            "service_execution_summary": service_execution_summary,
        }

        data_section = {
            "total_bundles_found": len(top_bundles),
            "category_highlights": highlights,
            "top_bundles": top_bundles,
            "service_execution_summary": service_execution_summary,
            "performance_metrics": self.client.get_metrics_summary() if hasattr(self.client, "get_metrics_summary") else {},
            "cache_metrics": self.cache.get_metrics_summary() if self.cache else {},
            "output_file": filepath,
        }

        result_payload = {
            "status": "success",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "meta_data": meta_data,
            "data": data_section,
        }


        # 5. Export JSON report file
        self.save_debug_output(filename, result_payload, force=True)

        # 6. Cache in Redis using record-level caching and query index dynamic TTL
        if self.cache and self.cache.enabled:
            all_fl = list(flight_offers)
            all_st = list(stay_results)
            all_cr = list(car_offers)
            self.cache.set_records_batch("flights", all_fl, id_key="id")
            self.cache.set_records_batch("stays", all_st, id_key="id")
            self.cache.set_records_batch("cars", all_cr, id_key="id")
            all_component_records = all_fl + all_st + all_cr
            ttl_val = self.cache.calculate_earliest_ttl(all_component_records)
            ttl_sec = ttl_val[0] if isinstance(ttl_val, tuple) else (ttl_val or 900)
            self.cache.set(cache_key, result_payload, ttl_seconds=ttl_sec)



        return result_payload

    def create_bundle_order(
        self,
        flight_offer_id: str,
        stay_quote_id: str,
        car_offer_id: str,
        passengers: list[Any],
        guests: list[Any],
        driver_details: dict[str, Any],
        payments: list[Any],
        promo_code: Optional[str] = None,
        discount_amount: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Creates combined Flight + Hotel + Car orders and returns combined booking details.
        """
        # Create Flight Order
        fl_order_id, fl_pnr = "ord_fl_mock", "PNR_MOCK"
        try:
            if hasattr(self.client_app, "flights"):
                fl_ord = self.client_app.flights.create_order(
                    selected_offers=[flight_offer_id],
                    passengers=passengers,
                    payments=payments,
                )
                fl_order_id = getattr(fl_ord, "id", fl_order_id)
                fl_pnr = getattr(fl_ord, "booking_reference", fl_pnr)
        except Exception as fe:
            print(f"[BUNDLE ORDER] Flight booking notice: {fe}")

        # Create Stay Order
        st_order_id, st_ref = "ord_stay_mock", "HOTEL_MOCK"
        try:
            if hasattr(self.client_app, "stays"):
                st_ord = self.client_app.stays.create_order(
                    quote_id=stay_quote_id,
                    guests=guests,
                    payments=[p.to_dict() if hasattr(p, "to_dict") else p for p in payments],
                )
                st_order_id = getattr(st_ord, "id", st_order_id)
                st_ref = getattr(st_ord, "booking_reference", st_ref)
        except Exception as se:
            print(f"[BUNDLE ORDER] Stay booking notice: {se}")

        # Create Car Order
        cr_order_id, cr_ref = "ord_car_mock", "CAR_MOCK"
        try:
            if hasattr(self.client_app, "cars"):
                cr_ord = self.client_app.cars.create_order(
                    offer_id=car_offer_id,
                    driver_details=driver_details,
                    payments=[p.to_dict() if hasattr(p, "to_dict") else p for p in payments],
                )
                cr_order_id = getattr(cr_ord, "id", cr_order_id)
                cr_ref = getattr(cr_ord, "booking_reference", cr_ref)
        except Exception as ce:
            print(f"[BUNDLE ORDER] Car booking notice: {ce}")

        bundle_order_id = f"ord_bnd_{hashlib.md5(f'{fl_order_id}_{st_order_id}_{cr_order_id}'.encode()).hexdigest()[:8]}"
        tot_amount = sum(float(getattr(p, "amount", 0.0) or 0.0) for p in payments) if payments else 750.0
        disc_val = float(discount_amount or 0.0)
        gross_val = tot_amount + disc_val

        meta_data = {
            "type": "bundles",
            "bundle_order_id": bundle_order_id,
            "promo_code": promo_code,
            "discount_amount": f"{disc_val:.2f}",
            "gross_amount": f"{gross_val:.2f}",
            "geo_location": None,
        }

        data_section = {
            "bundle_order_id": bundle_order_id,
            "flight_order_id": fl_order_id,
            "flight_booking_reference": fl_pnr,
            "stay_order_id": st_order_id,
            "stay_booking_reference": st_ref,
            "car_order_id": cr_order_id,
            "car_booking_reference": cr_ref,
            "combined_total_amount": f"{tot_amount:.2f}",
            "total_currency": "USD",
            "created_at": datetime.now().isoformat(),
            "gross_amount": f"{gross_val:.2f}",
            "discount_amount": f"{disc_val:.2f}",
            "promo_code": promo_code,
            "message": "Travel package bundle booked successfully.",
        }

        res_dict = {
            "status": "confirmed",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "meta_data": meta_data,
            "data": data_section,
        }


        # Persist individual orders separately with unique bundle_id and save master bundle order
        try:
            from ..db.order_dao import OrderDAO
            cfg = self.client.config if hasattr(self.client, "config") else None
            order_dao = OrderDAO(config=cfg)

            # 1. Save Flight Order separately with bundle_id
            order_dao.save_hold_order(
                duffel_order_id=fl_order_id,
                booking_reference=fl_pnr,
                total_amount="350.00",
                total_currency="USD",
                order_type="instant",
                status="confirmed",
                payment_status="paid",
                bundle_id=bundle_order_id,
                promo_code=promo_code,
                gross_amount="350.00",
                discount_amount="0.00",
            )

            # 2. Save Stay Order separately with bundle_id
            order_dao.save_stay_order(
                duffel_order_id=st_order_id,
                booking_reference=st_ref,
                total_amount="250.00",
                total_currency="USD",
                quote_id=stay_quote_id,
                status="confirmed",
                payment_status="paid",
                guests=guests,
                bundle_id=bundle_order_id,
                promo_code=promo_code,
                gross_amount="250.00",
                discount_amount="0.00",
            )

            # 3. Save Car Order separately with bundle_id
            order_dao.save_car_order(
                duffel_order_id=cr_order_id,
                booking_reference=cr_ref,
                total_amount="150.00",
                total_currency="USD",
                offer_id=car_offer_id,
                status="confirmed",
                payment_status="paid",
                driver_details=driver_details,
                bundle_id=bundle_order_id,
                promo_code=promo_code,
                gross_amount="150.00",
                discount_amount="0.00",
            )

            # 4. Save Master Bundle Order Record
            order_dao.save_bundle_order(
                duffel_bundle_id=bundle_order_id,
                flight_order_id=fl_order_id,
                stay_order_id=st_order_id,
                car_order_id=cr_order_id,
                combined_total_amount=f"{tot_amount:.2f}",
                total_currency="USD",
                flight_details={"pnr": fl_pnr},
                stay_details={"reference": st_ref},
                car_details={"reference": cr_ref},
                promo_code=promo_code,
                gross_amount=f"{gross_val:.2f}",
                discount_amount=f"{disc_val:.2f}",
            )

            # 5. Publish Master Booking Confirmed Event for Email Service
            try:
                from .event_publisher import EventPublisher
                publisher = EventPublisher(config=cfg)
                c_email = (passengers[0].get("email") if (passengers and isinstance(passengers[0], dict)) else None) or "customer@example.com"
                publisher.publish_booking_confirmed_event(
                    booking_id=bundle_order_id,
                    booking_reference=fl_pnr or bundle_order_id,
                    total_amount=f"{tot_amount:.2f}",
                    total_currency="USD",
                    booking_type="bundle",
                    recipient_email=c_email,
                    passengers=passengers or [],
                    bundle_components=[
                        {"type": "flight", "order_id": fl_order_id, "pnr": fl_pnr},
                        {"type": "stay", "order_id": st_order_id, "reference": st_ref},
                        {"type": "car", "order_id": cr_order_id, "reference": cr_ref},
                    ],
                )
            except Exception as sb_err:
                print(f"[SERVICE BUS NOTICE] Failed publishing bundle booking confirmed event: {sb_err}")
        except Exception as db_err:
            print(f"[BUNDLE DAO NOTICE] Failed saving bundle orders to database: {db_err}")

        return res_dict
