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
        
        origin = slices[0]["origin"] if slices else "JFK"
        destination = slices[0]["destination"] if slices else "LHR"
        departure_date = slices[0]["departure_date"] if slices else "2026-10-01"

        return {
            "data": {
                "id": req_id,
                "created_at": "2026-08-25T12:00:00Z",
                "live_mode": False,
                "slices": slices,
                "passengers": payload.get("passengers", [{"type": "adult"}]),
                "cabin_class": payload.get("cabin_class", "economy"),
                "offers": [
                    {
                        "id": offer_id,
                        "live_mode": False,
                        "created_at": "2026-08-25T12:00:00Z",
                        "expires_at": "2026-08-25T14:00:00Z",
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
        return {
            "data": {
                "id": s_id,
                "location": payload.get("location", {"name": "New York"}),
                "check_in_date": payload.get("check_in_date", "2026-10-01"),
                "check_out_date": payload.get("check_out_date", "2026-10-05"),
                "results": [
                    {
                        "id": f"st_res_mock_{uuid.uuid4().hex[:8]}",
                        "search_request_id": s_id,  # Added: needed to fetch rates
                        "accommodation": {
                            "id": "acc_mock_1",
                            "name": "Grand Mock Hotel",
                            "rating": 5
                        },
                        "rates": [
                            {
                                "id": f"rat_mock_{uuid.uuid4().hex[:8]}",
                                "quote_id": f"quo_mock_{uuid.uuid4().hex[:8]}",  # Added: needed for booking
                                "total_amount": "600.00",
                                "total_currency": "USD",
                                "board_type": "room_only",
                                "description": "Standard Room",
                                "cancellation_timeline": [],
                                "available_rooms": 5
                            }
                        ],
                        "created_at": "2026-08-25T10:00:00Z",
                        "cheapest_rate_total_amount": "600.00",
                        "cheapest_rate_currency": "USD"
                    }
                ]
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
        return {
            "data": {
                "offers": [
                    {
                        "id": f"cro_mock_{uuid.uuid4().hex[:8]}",
                        "supplier": {"name": "Hertz"},
                        "vehicle": {"category": "SUV", "name": "Ford Explorer"},
                        "total_amount": "250.00",
                        "total_currency": "USD"
                    }
                ]
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
