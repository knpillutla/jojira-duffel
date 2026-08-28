"""
Mock Travel Provider Adapter for testing and offline execution.
"""

import time
import uuid
from typing import Any, Optional

from .base import BaseProviderAdapter


class MockProviderAdapter(BaseProviderAdapter):
    """
    Mock Provider Adapter returning mock responses compliant with the Duffel service schema.
    """

    def __init__(self, provider_id: str = "mock"):
        self.provider_id = provider_id

    # --- Flight Operations ---

    def search_flights(self, payload: dict[str, Any]) -> dict[str, Any]:
        req_id = f"orq_mock_{uuid.uuid4().hex[:8]}"
        offer_id = f"off_mock_{uuid.uuid4().hex[:8]}"
        slices = payload.get("slices", [])
        
        if slices and isinstance(slices[0], dict):
            origin = slices[0].get("origin", "JFK")
            destination = slices[0].get("destination", "LHR")
            departure_date = slices[0].get("departure_date", "2026-10-01")
        elif slices:
            origin = getattr(slices[0], "origin", "JFK")
            destination = getattr(slices[0], "destination", "LHR")
            departure_date = getattr(slices[0], "departure_date", "2026-10-01")
        else:
            origin = "JFK"
            destination = "LHR"
            departure_date = "2026-10-01"


        from datetime import datetime, timezone, timedelta
        now_iso = datetime.now(timezone.utc).isoformat()
        exp_iso = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        return {
            "data": {
                "id": req_id,
                "created_at": now_iso,
                "live_mode": False,
                "slices": slices,
                "passengers": payload.get("passengers", [{"type": "adult"}]),
                "cabin_class": payload.get("cabin_class", "economy"),
                "offers": [
                    {
                        "id": offer_id,
                        "live_mode": False,
                        "created_at": now_iso,
                        "expires_at": exp_iso,
                        "total_amount": "450.00",
                        "total_currency": "USD",

                        "tax_amount": "50.00",
                        "tax_currency": "USD",
                        "base_amount": "400.00",
                        "base_currency": "USD",
                        "owner": {
                            "iata_code": "AA",
                            "name": "American Airlines",
                            "logo_symbol_url": "https://assets.duffel.com/img/airlines/for-light-background/full-color-logo/AA.svg"
                        },
                        "slices": [
                            {
                                "id": f"sli_mock_{uuid.uuid4().hex[:8]}",
                                "origin": {"iata_code": origin, "name": origin, "city_name": origin},
                                "destination": {"iata_code": destination, "name": destination, "city_name": destination},
                                "duration": "PT7H30M",
                                "segments": [
                                    {
                                        "id": f"seg_mock_{uuid.uuid4().hex[:8]}",
                                        "origin": {"iata_code": origin, "name": origin},
                                        "destination": {"iata_code": destination, "name": destination},
                                        "departing_at": f"{departure_date}T08:00:00",
                                        "arriving_at": f"{departure_date}T15:30:00",
                                        "operating_carrier": {"iata_code": "AA", "name": "American Airlines"},
                                        "marketing_carrier": {"iata_code": "AA", "name": "American Airlines"},
                                        "operating_carrier_flight_number": "100",
                                        "marketing_carrier_flight_number": "100",
                                        "stops": []
                                    }
                                ]
                            }
                        ],
                        "passengers": [
                            {
                                "id": f"pas_mock_{uuid.uuid4().hex[:8]}",
                                "type": "adult"
                            }
                        ]
                    }
                ]
            }
        }

    def get_offer_request(self, offer_request_id: str) -> dict[str, Any]:
        return self.search_flights({"slices": [{"origin": "JFK", "destination": "LHR", "departure_date": "2026-10-01"}]})

    def list_offers(self, offer_request_id: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        res = self.search_flights({"slices": [{"origin": "JFK", "destination": "LHR", "departure_date": "2026-10-01"}]})
        return {"data": res["data"]["offers"]}

    def get_offer(self, offer_id: str) -> dict[str, Any]:
        res = self.search_flights({"slices": [{"origin": "JFK", "destination": "LHR", "departure_date": "2026-10-01"}]})
        offer = res["data"]["offers"][0]
        offer["id"] = offer_id
        return {"data": offer}

    def create_flight_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        order_id = f"ord_mock_{uuid.uuid4().hex[:8]}"
        return {
            "data": {
                "id": order_id,
                "live_mode": False,
                "created_at": "2026-08-25T12:00:00Z",
                "booking_reference": "MOCKREF123",
                "total_amount": payload.get("payments", [{}])[0].get("amount", "450.00") if payload.get("payments") else "450.00",
                "total_currency": payload.get("payments", [{}])[0].get("currency", "USD") if payload.get("payments") else "USD",
                "passengers": payload.get("passengers", []),
                "slices": [],
                "documents": []
            }
        }

    def pay_flight_order(self, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "data": {
                "id": order_id,
                "status": "paid",
                "paid_at": "2026-08-25T12:00:00Z"
            }
        }

    def get_flight_order(self, order_id: str) -> dict[str, Any]:
        return self.create_flight_order({})

    def list_flight_orders(self, limit: int = 50) -> dict[str, Any]:
        return {"data": [self.create_flight_order({})["data"]]}

    def cancel_flight_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "data": {
                "id": f"cnl_mock_{uuid.uuid4().hex[:8]}",
                "order_id": payload.get("order_id", "ord_mock"),
                "refund_amount": "450.00",
                "refund_currency": "USD",
                "status": "confirmed"
            }
        }

    def tokenize_card(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "data": {
                "id": f"tok_mock_{uuid.uuid4().hex[:8]}",
                "live_mode": False,
                "created_at": "2026-08-25T12:00:00Z"
            }
        }

    def create_component_client_key(self) -> dict[str, Any]:
        return {
            "data": {
                "client_key": f"ck_mock_{uuid.uuid4().hex[:16]}"
            }
        }

    def create_three_d_secure_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "data": {
                "id": f"3ds_mock_{uuid.uuid4().hex[:8]}",
                "status": "authenticated"
            }
        }

    # --- Stay Operations ---

    def search_stays(self, payload: dict[str, Any]) -> dict[str, Any]:
        s_id = f"str_mock_{uuid.uuid4().hex[:8]}"
        loc_val = payload.get("location") or {}
        loc_name = loc_val.get("name") if isinstance(loc_val, dict) else str(loc_val)
        if not loc_name or loc_name == "{}":
            loc_name = "City Center"

        hotel_brands = [
            "Grand Hyatt", "Marriott Marquis", "Hilton Garden Inn", "Ritz-Carlton", "Four Seasons",
            "InterContinental", "Sheraton Suites", "Westin Resort & Spa", "W Hotel", "St. Regis",
            "Kimpton Hotel", "Hyatt Regency", "Radisson Blu", "DoubleTree by Hilton", "Holiday Inn Express",
            "Hampton Inn & Suites", "Courtyard by Marriott", "Fairfield Inn", "Residence Inn", "Embassy Suites",
            "AC Hotel", "Aloft Hotel", "JW Marriott", "Crowne Plaza", "Omni Hotel",
            "Waldorf Astoria", "Conrad Hotel", "Fairmont Resort", "Sofitel Luxury Hotel", "Pullman Hotel",
            "Novotel City Center", "Mercure Hotel", "Meliá Resort", "NH Collection", "Banyan Tree",
            "Mandarin Oriental", "Rosewood Hotel", "Peninsula", "Shangri-La", "Aman Resort",
            "Six Senses", "One&Only", "Belmond Hotel", "CitizenM", "Mama Shelter",
            "Generator Hostels", "YOTEL", "Standard Hotel", "Ace Hotel", "Hoxton Hotel"
        ]

        results = []
        for i in range(50):
            brand = hotel_brands[i % len(hotel_brands)]
            h_id = f"acc_mock_{i+1}"
            rating = 5 if i % 3 == 0 else (4 if i % 2 == 0 else 3)
            base_amount = 120.0 + (i * 12.5)

            rates = [
                {
                    "id": f"rat_mock_{(i*2)+1}_{uuid.uuid4().hex[:6]}",
                    "quote_id": f"quo_mock_{(i*2)+1}_{uuid.uuid4().hex[:6]}",
                    "total_amount": f"{base_amount:.2f}",
                    "total_currency": "USD",
                    "board_type": "room_only" if i % 2 == 0 else "breakfast",
                    "description": "Standard Deluxe Room",
                    "cancellation_timeline": [],
                    "available_rooms": (i % 5) + 1
                },
                {
                    "id": f"rat_mock_{(i*2)+2}_{uuid.uuid4().hex[:6]}",
                    "quote_id": f"quo_mock_{(i*2)+2}_{uuid.uuid4().hex[:6]}",
                    "total_amount": f"{(base_amount * 1.25):.2f}",
                    "total_currency": "USD",
                    "board_type": "all_inclusive" if i % 3 == 0 else "breakfast",
                    "description": "Executive Ocean/City View Suite",
                    "cancellation_timeline": [],
                    "available_rooms": (i % 3) + 1
                }
            ]

            results.append({
                "id": f"st_res_mock_{i+1}_{uuid.uuid4().hex[:6]}",
                "search_request_id": s_id,
                "accommodation": {
                    "id": h_id,
                    "name": f"{brand} {loc_name}",
                    "rating": rating
                },
                "rates": rates,
                "created_at": "2026-08-25T10:00:00Z",
                "cheapest_rate_total_amount": f"{base_amount:.2f}",
                "cheapest_rate_currency": "USD"
            })

        return {
            "data": {
                "id": s_id,
                "location": {"name": loc_name},
                "check_in_date": payload.get("check_in_date", "2026-10-01"),
                "check_out_date": payload.get("check_out_date", "2026-10-05"),
                "results": results
            }
        }

    def get_stay_search_result(self, search_result_id: str) -> dict[str, Any]:
        return self.search_stays({})

    def get_stay_rates(self, search_result_id: str) -> dict[str, Any]:
        return {
            "data": [
                {
                    "id": f"rat_mock_{uuid.uuid4().hex[:8]}",
                    "quote_id": f"quo_mock_{uuid.uuid4().hex[:8]}",  # Added: needed for booking
                    "total_amount": "600.00",
                    "total_currency": "USD",
                    "board_type": "room_only",
                    "description": "Standard Room",
                    "cancellation_timeline": [],
                    "available_rooms": 5
                },
                {
                    "id": f"rat_mock_{uuid.uuid4().hex[:8]}",
                    "quote_id": f"quo_mock_{uuid.uuid4().hex[:8]}",  # Added: needed for booking
                    "total_amount": "750.00",
                    "total_currency": "USD",
                    "board_type": "breakfast",
                    "description": "Deluxe Room with Breakfast",
                    "cancellation_timeline": [],
                    "available_rooms": 3
                }
            ]
        }

    def create_stay_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "data": {
                "id": f"sto_mock_{uuid.uuid4().hex[:8]}",
                "status": "confirmed",
                "total_amount": "600.00",
                "total_currency": "USD"
            }
        }

    def get_stay_order(self, order_id: str) -> dict[str, Any]:
        return self.create_stay_order({})

    def cancel_stay_order(self, order_id: str) -> dict[str, Any]:
        return {
            "data": {
                "id": f"stc_mock_{uuid.uuid4().hex[:8]}",
                "order_id": order_id,
                "status": "cancelled"
            }
        }

    # --- Car Operations ---

    def search_cars(self, payload: dict[str, Any]) -> dict[str, Any]:
        suppliers = ["Hertz", "Avis", "Enterprise", "Budget", "National", "Sixt", "Dollar", "Thrifty", "Alamo", "Europcar"]
        vehicles = [
            ("Compact", "Toyota Corolla"), ("Compact", "Honda Civic"), ("Economy", "Hyundai Elantra"),
            ("Economy", "Nissan Versa"), ("Midsize", "Toyota Camry"), ("Midsize", "Honda Accord"),
            ("Full-size", "Chevrolet Malibu"), ("Full-size", "Nissan Altima"), ("SUV", "Tesla Model Y"),
            ("SUV", "Ford Explorer"), ("SUV", "Jeep Grand Cherokee"), ("SUV", "Toyota RAV4"),
            ("SUV", "Chevrolet Tahoe"), ("Luxury", "BMW 3 Series"), ("Luxury", "Mercedes-Benz C-Class"),
            ("Luxury", "Audi A4"), ("Luxury", "Genesis G80"), ("Luxury SUV", "Cadillac Escalade"),
            ("Luxury SUV", "Porsche Macan"), ("Convertible", "Ford Mustang Convertible"),
            ("Convertible", "Chevrolet Camaro Convertible"), ("Electric", "Tesla Model 3"),
            ("Electric", "Hyundai Ioniq 5"), ("Minivan", "Chrysler Pacifica"), ("Minivan", "Honda Odyssey")
        ]

        category_images = {
            "Compact": "https://images.unsplash.com/photo-1590362891991-f776e747a588?auto=format&fit=crop&w=800&q=80",
            "Economy": "https://images.unsplash.com/photo-1541899481282-d53bffe3c35d?auto=format&fit=crop&w=800&q=80",
            "Midsize": "https://images.unsplash.com/photo-1621007947382-bb3c3994e3fb?auto=format&fit=crop&w=800&q=80",
            "Full-size": "https://images.unsplash.com/photo-1617814076367-b759c7d7e738?auto=format&fit=crop&w=800&q=80",
            "SUV": "https://images.unsplash.com/photo-1563720223185-11003d516935?auto=format&fit=crop&w=800&q=80",
            "Luxury": "https://images.unsplash.com/photo-1555215695-3004980ad54e?auto=format&fit=crop&w=800&q=80",
            "Luxury SUV": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
            "Convertible": "https://images.unsplash.com/photo-1584345604476-8ec5e12e42dd?auto=format&fit=crop&w=800&q=80",
            "Electric": "https://images.unsplash.com/photo-1560958089-b8a1929cea89?auto=format&fit=crop&w=800&q=80",
            "Minivan": "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80",
        }

        offers = []
        for i in range(50):
            sup = suppliers[i % len(suppliers)]
            cat, model = vehicles[i % len(vehicles)]
            price = 35.0 + (i * 6.5)
            img_url = category_images.get(cat, "https://images.unsplash.com/photo-1541899481282-d53bffe3c35d?auto=format&fit=crop&w=800&q=80")
            sup_logo = f"https://assets.duffel.com/img/car-suppliers/{sup.lower()}.svg"

            vehicle_dict = {
                "category": cat,
                "name": f"{model} ({cat})",
                "transmission": "automatic",
                "passenger_capacity": 5 if cat not in ["Minivan", "Luxury SUV"] else 7,
                "baggage_capacity": 3,
                "air_conditioning": True,
                "image_url": img_url,
                "images": [img_url],
                "media": [{"url": img_url, "type": "image/jpeg"}],
                "photos": [{"url": img_url}]
            }

            offers.append({
                "id": f"cro_mock_{i+1}_{uuid.uuid4().hex[:6]}",
                "image_url": img_url,
                "supplier": {
                    "name": sup,
                    "code": sup[:3].upper(),
                    "logo_url": sup_logo
                },
                "vehicle": vehicle_dict,
                "total_amount": f"{price:.2f}",
                "total_currency": "USD"
            })

        return {
            "data": {
                "offers": offers
            }
        }



    def get_car_offer(self, offer_id: str) -> dict[str, Any]:
        return {
            "data": {
                "id": offer_id,
                "supplier": {"name": "Hertz"},
                "vehicle": {"category": "SUV", "name": "Ford Explorer"},
                "total_amount": "250.00",
                "total_currency": "USD"
            }
        }

    def create_car_quote(self, rate_id: str) -> dict[str, Any]:
        return {
            "data": {
                "id": f"qut_mock_{uuid.uuid4().hex[:8]}",
                "rate_id": rate_id,
                "supplier": {"name": "Hertz"},
                "total_amount": "250.00",
                "total_currency": "USD"
            }
        }

    def create_car_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "data": {
                "id": f"cro_ord_{uuid.uuid4().hex[:8]}",
                "status": "confirmed",
                "total_amount": "250.00",
                "total_currency": "USD"
            }
        }

    def get_car_order(self, order_id: str) -> dict[str, Any]:
        return self.create_car_order({})

    def cancel_car_order(self, offer_id_or_order_id: str) -> dict[str, Any]:
        return {
            "data": {
                "id": f"crc_mock_{uuid.uuid4().hex[:8]}",
                "order_id": offer_id_or_order_id,
                "status": "cancelled"
            }
        }

    # --- Places & Airports Operations ---

    def list_airports(self, limit: int = 200) -> dict[str, Any]:
        return {
            "data": [
                {"id": "arp_alb_us", "name": "Albany International Airport", "iata_code": "ALB", "city_name": "Albany", "latitude": 42.7483, "longitude": -73.8017},
                {"id": "arp_atl_us", "name": "Hartsfield-Jackson Atlanta International Airport", "iata_code": "ATL", "city_name": "Atlanta", "latitude": 33.6407, "longitude": -84.4277},
                {"id": "arp_jfk_us", "name": "John F. Kennedy International Airport", "iata_code": "JFK", "city_name": "New York", "latitude": 40.6413, "longitude": -73.7781},
                {"id": "arp_lhr_uk", "name": "London Heathrow Airport", "iata_code": "LHR", "city_name": "London", "latitude": 51.4700, "longitude": -0.4543},
                {"id": "arp_cdg_fr", "name": "Paris Charles de Gaulle Airport", "iata_code": "CDG", "city_name": "Paris", "latitude": 49.0097, "longitude": 2.5479},
            ]
        }

    def list_cities(self, limit: int = 200) -> dict[str, Any]:
        return {
            "data": [
                {"id": "cit_alb_us", "name": "Albany", "iata_code": "ALB", "latitude": 42.6526, "longitude": -73.7562},
                {"id": "cit_nyc_us", "name": "New York", "iata_code": "NYC", "latitude": 40.7128, "longitude": -74.0060},
                {"id": "cit_lon_uk", "name": "London", "iata_code": "LON", "latitude": 51.5074, "longitude": -0.1278},
                {"id": "cit_par_fr", "name": "Paris", "iata_code": "PAR", "latitude": 48.8566, "longitude": 2.3522},
            ]
        }

    def search_places(self, query: str) -> dict[str, Any]:
        return self.list_airports(limit=10)

