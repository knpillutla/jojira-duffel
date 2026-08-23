"""
Interactive slot filling module for missing flight, stay, and car search parameters.
"""

from datetime import datetime, timedelta
from typing import Any, Optional


def prompt_input(label: str, default: str = "", required: bool = True) -> str:
    """Prompt user for input with default support and validation."""
    prompt_str = f"{label}"
    if default:
        prompt_str += f" [{default}]"
    prompt_str += ": "

    while True:
        try:
            val = input(prompt_str).strip()
            if not val and default:
                return default
            if not val and required:
                print("  [!] This field is required. Please enter a value.")
                continue
            return val
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled.")
            raise SystemExit(0)


def fill_optimized_flight_slots(extracted: dict[str, Any]) -> dict[str, Any]:
    """
    Prompt interactively for Optimized Flight Search parameters:
      - Origin & Destination
      - Target departure date
      - Trip duration (number of days to travel)
      - Date flexibility window (+/- flex days)
    """
    extracted_slices = extracted.get("slices", [])
    first_slice = extracted_slices[0] if extracted_slices else {}

    orig = first_slice.get("origin") or ""
    dest = first_slice.get("destination") or ""
    target_date = first_slice.get("departure_date") or ""

    second_slice = extracted_slices[1] if len(extracted_slices) > 1 else {}
    target_return_date = second_slice.get("departure_date") or ""

    if orig:
        print(f"  * Extracted Origin: {orig}")
    if dest:
        print(f"  * Extracted Destination: {dest}")
    if target_date:
        print(f"  * Extracted Target Date: {target_date}")
    if target_return_date:
        print(f"  * Extracted Target Return Date: {target_return_date}")

    orig = prompt_input("  Enter Origin Airport IATA Code (e.g. LHR, JFK, LAX)", default=orig or "LHR")
    dest = prompt_input("  Enter Destination Airport IATA Code (e.g. JFK, SFO, CDG)", default=dest or "JFK")

    if not target_date:
        default_target = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        target_date = prompt_input("  Enter Target Departure Date (YYYY-MM-DD)", default=default_target)

    target_dep_dt = datetime.strptime(target_date, "%Y-%m-%d")
    default_ret_date = target_return_date or (target_dep_dt + timedelta(days=7)).strftime("%Y-%m-%d")
    target_return_date = prompt_input("  Enter Target Return Date (YYYY-MM-DD)", default=default_ret_date)

    target_ret_dt = datetime.strptime(target_return_date, "%Y-%m-%d")
    if target_ret_dt < target_dep_dt:
        print("  [!] Target Return Date cannot be before Target Departure Date. Adjusting return date.")
        target_ret_dt = target_dep_dt + timedelta(days=7)
        target_return_date = target_ret_dt.strftime("%Y-%m-%d")

    max_allowed_duration = (target_ret_dt - target_dep_dt).days
    if max_allowed_duration < 1:
        max_allowed_duration = 1

    flex_days = 0

    # Prompt and validate MAXIMUM Trip Duration (must be <= max_allowed_duration)
    while True:
        max_dur_str = prompt_input(
            f"  Enter MAXIMUM Trip Duration in Days (1 to {max_allowed_duration})",
            default=str(max_allowed_duration)
        )
        try:
            max_duration_days = int(max_dur_str)
            if 1 <= max_duration_days <= max_allowed_duration:
                break
            else:
                print(
                    f"  [!] Error: Maximum trip duration cannot exceed {max_allowed_duration} days "
                    f"(the interval between {target_date} and {target_return_date}). Please try again."
                )
        except ValueError:
            print("  [!] Invalid number. Please enter an integer.")

    # Prompt and validate MINIMUM Trip Duration (must be 1 <= min <= max_duration_days)
    default_min = max_duration_days
    while True:
        min_dur_str = prompt_input(
            f"  Enter MINIMUM Trip Duration in Days (1 to {max_duration_days})",
            default=str(default_min)
        )
        try:
            min_duration_days = int(min_dur_str)
            if 1 <= min_duration_days <= max_duration_days:
                break
            else:
                print(
                    f"  [!] Error: Minimum trip duration must be between 1 and {max_duration_days} days. Please try again."
                )
        except ValueError:
            print("  [!] Invalid number. Please enter an integer.")

    cabin = extracted.get("cabin_class") or "economy"
    cabin_class = prompt_input(
        "  Enter Cabin Class (economy, premium_economy, business, first)", default=cabin, required=False
    ).lower()

    pax_count = str(extracted.get("passengers_count") or 1)
    passengers_count = int(
        prompt_input("  Enter Number of Adult Passengers", default=pax_count, required=False)
    )

    return {
        "origin": orig,
        "destination": dest,
        "target_date": target_date,
        "target_return_date": target_return_date,
        "min_duration_days": min_duration_days,
        "max_duration_days": max_duration_days,
        "flex_days": flex_days,
        "cabin_class": cabin_class,
        "passengers_count": passengers_count,
    }


def fill_flight_slots(extracted: dict[str, Any]) -> dict[str, Any]:
    """
    Review extracted flight parameters and interactively prompt for trip type:
      [1] One-way
      [2] Round trip (Two-way)
      [3] Multi-city
    """
    print("\n--- Flight Search Parameter Extraction ---")

    # 1. Determine Trip Type
    trip_type = extracted.get("trip_type")
    if not trip_type:
        print("\nSelect Trip Type:")
        print("  [1] One-way")
        print("  [2] Round trip (Two-way)")
        print("  [3] Multi-city")
        type_choice = prompt_input("Enter choice (1-3)", default="1")
        if type_choice == "2":
            trip_type = "round_trip"
        elif type_choice == "3":
            trip_type = "multi_city"
        else:
            trip_type = "one_way"
    else:
        print(f"  * Extracted Trip Type: {trip_type.replace('_', ' ').title()}")

    extracted["trip_type"] = trip_type

    extracted_slices = extracted.get("slices", [])
    final_slices = []

    if trip_type == "one_way":
        first_slice = extracted_slices[0] if extracted_slices else {}
        print("\n[Leg 1 - One-way Flight Details]")
        orig = first_slice.get("origin") or ""
        dest = first_slice.get("destination") or ""
        dep_date = first_slice.get("departure_date") or ""

        if orig:
            print(f"  * Extracted Origin: {orig}")
        if dest:
            print(f"  * Extracted Destination: {dest}")
        if dep_date:
            print(f"  * Extracted Departure Date: {dep_date}")

        orig = prompt_input("  Enter Origin Airport IATA Code (e.g. LHR, JFK, LAX)", default=orig or "LHR")
        dest = prompt_input("  Enter Destination Airport IATA Code (e.g. JFK, SFO, CDG)", default=dest or "JFK")

        if not dep_date:
            default_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            dep_date = prompt_input("  Enter Departure Date (YYYY-MM-DD)", default=default_date)

        final_slices.append({"origin": orig, "destination": dest, "departure_date": dep_date})

    elif trip_type == "round_trip":
        leg1 = extracted_slices[0] if len(extracted_slices) >= 1 else {}
        leg2 = extracted_slices[1] if len(extracted_slices) >= 2 else {}

        print("\n[Leg 1 - Outbound Flight]")
        orig1 = leg1.get("origin") or ""
        dest1 = leg1.get("destination") or ""
        dep_date1 = leg1.get("departure_date") or ""

        orig1 = prompt_input("  Enter Origin Airport IATA Code (e.g. LHR, JFK, LAX)", default=orig1 or "LHR")
        dest1 = prompt_input("  Enter Destination Airport IATA Code (e.g. JFK, SFO, CDG)", default=dest1 or "JFK")

        if not dep_date1:
            default_date1 = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            dep_date1 = prompt_input("  Enter Outbound Departure Date (YYYY-MM-DD)", default=default_date1)

        final_slices.append({"origin": orig1, "destination": dest1, "departure_date": dep_date1})

        print("\n[Leg 2 - Return Flight]")
        orig2 = leg2.get("origin") or dest1
        dest2 = leg2.get("destination") or orig1
        dep_date2 = leg2.get("departure_date") or ""

        orig2 = prompt_input("  Enter Return Origin Airport", default=orig2)
        dest2 = prompt_input("  Enter Return Destination Airport", default=dest2)

        if not dep_date2:
            out_dt = datetime.strptime(dep_date1, "%Y-%m-%d")
            default_date2 = (out_dt + timedelta(days=7)).strftime("%Y-%m-%d")
            dep_date2 = prompt_input("  Enter Return Departure Date (YYYY-MM-DD)", default=default_date2)

        final_slices.append({"origin": orig2, "destination": dest2, "departure_date": dep_date2})

    elif trip_type == "multi_city":
        print("\n[Multi-city Flight Setup]")
        existing_count = len(extracted_slices)
        count_str = prompt_input("  Enter Number of Flight Legs", default=str(existing_count if existing_count > 1 else 3))
        num_legs = max(2, int(count_str))

        prev_dest = "LHR"
        prev_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        for i in range(num_legs):
            leg_info = extracted_slices[i] if i < len(extracted_slices) else {}
            print(f"\n[Leg {i+1} Details]")

            default_orig = leg_info.get("origin") or prev_dest
            default_dest = leg_info.get("destination") or ("JFK" if default_orig != "JFK" else "CDG")

            orig = prompt_input(f"  Leg {i+1} Origin Airport", default=default_orig)
            dest = prompt_input(f"  Leg {i+1} Destination Airport", default=default_dest)

            default_dep = leg_info.get("departure_date")
            if not default_dep:
                try:
                    last_dt = datetime.strptime(prev_date, "%Y-%m-%d")
                    default_dep = (last_dt + timedelta(days=5)).strftime("%Y-%m-%d")
                except Exception:
                    default_dep = (datetime.now() + timedelta(days=30 + i * 5)).strftime("%Y-%m-%d")

            dep_date = prompt_input(f"  Leg {i+1} Departure Date (YYYY-MM-DD)", default=default_dep)

            final_slices.append({"origin": orig, "destination": dest, "departure_date": dep_date})
            prev_dest = dest
            prev_date = dep_date

    extracted["slices"] = final_slices

    # Cabin Class & Passenger count
    cabin = extracted.get("cabin_class") or "economy"
    extracted["cabin_class"] = prompt_input(
        "\n  Enter Cabin Class (economy, premium_economy, business, first)", default=cabin, required=False
    ).lower()

    pax_count = str(extracted.get("passengers_count") or 1)
    extracted["passengers_count"] = int(
        prompt_input("  Enter Number of Adult Passengers", default=pax_count, required=False)
    )

    return extracted


def fill_stay_slots(extracted: dict[str, Any]) -> dict[str, Any]:
    """
    Review extracted stay/hotel parameters and interactively prompt for missing fields.
    """
    print("\n--- Hotel / Stay Search Parameter Extraction ---")
    if extracted.get("location"):
        print(f"  * Extracted Location: {extracted['location']}")
    if extracted.get("check_in_date"):
        print(f"  * Extracted Check-in Date: {extracted['check_in_date']}")
    if extracted.get("check_out_date"):
        print(f"  * Extracted Check-out Date: {extracted['check_out_date']}")

    if not extracted.get("location"):
        extracted["location"] = prompt_input("  Enter City or Airport / Location (e.g. New York, London)", default="New York")

    if not extracted.get("check_in_date"):
        default_in = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        extracted["check_in_date"] = prompt_input("  Enter Check-in Date (YYYY-MM-DD)", default=default_in)

    if not extracted.get("check_out_date"):
        in_dt = datetime.strptime(extracted["check_in_date"], "%Y-%m-%d")
        default_out = (in_dt + timedelta(days=4)).strftime("%Y-%m-%d")
        extracted["check_out_date"] = prompt_input("  Enter Check-out Date (YYYY-MM-DD)", default=default_out)

    guests = str(extracted.get("guests_count") or 1)
    extracted["guests_count"] = int(prompt_input("  Enter Number of Guests", default=guests, required=False))

    rooms = str(extracted.get("rooms") or 1)
    extracted["rooms"] = int(prompt_input("  Enter Number of Rooms", default=rooms, required=False))

    return extracted


def fill_car_slots(extracted: dict[str, Any]) -> dict[str, Any]:
    """
    Review extracted car rental parameters and interactively prompt for missing fields.
    """
    print("\n--- Car Rental Search Parameter Extraction ---")
    if extracted.get("pickup_location"):
        print(f"  * Extracted Pickup Location: {extracted['pickup_location']}")
    if extracted.get("dropoff_location"):
        print(f"  * Extracted Dropoff Location: {extracted['dropoff_location']}")
    if extracted.get("pickup_datetime"):
        print(f"  * Extracted Pickup Date: {extracted['pickup_datetime']}")

    if not extracted.get("pickup_location"):
        extracted["pickup_location"] = prompt_input("  Enter Pickup Airport IATA / Location (e.g. LAX, JFK)", default="LAX")

    if not extracted.get("dropoff_location"):
        extracted["dropoff_location"] = prompt_input("  Enter Dropoff Location", default=extracted["pickup_location"])

    if not extracted.get("pickup_datetime"):
        default_pick = (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%dT10:00:00Z")
        extracted["pickup_datetime"] = prompt_input("  Enter Pickup Date & Time (YYYY-MM-DDTHH:MM:SSZ)", default=default_pick)

    if not extracted.get("dropoff_datetime"):
        default_drop = (datetime.now() + timedelta(days=25)).strftime("%Y-%m-%dT10:00:00Z")
        extracted["dropoff_datetime"] = prompt_input("  Enter Dropoff Date & Time (YYYY-MM-DDTHH:MM:SSZ)", default=default_drop)

    age = str(extracted.get("driver_age") or 30)
    extracted["driver_age"] = int(prompt_input("  Enter Primary Driver Age", default=age, required=False))

    return extracted
