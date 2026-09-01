"""
Prompt Construction Engine for Travel Planner, Intent Extraction, and Modalities.
Assembles tailored, modular prompt components across providers, styles, and modalities.
"""

from typing import Any, Optional
from .loader import PromptLoader


def build_planner_system_prompt(
    config: Any,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Loads system prompt for specific provider-model template with fallback hierarchy."""
    prov = provider or getattr(config, "llm_planner_provider", "") or getattr(config, "llm_provider", "openai") or "openai"
    mod = model or getattr(config, f"{prov}_planner_model", "") or getattr(config, f"{prov}_model", "gpt-4o") or "gpt-4o"

    loaded = PromptLoader.load_prompt("planner_system_prompt", provider=prov, model=mod, config=config)
    if loaded:
        return loaded

    return (
        "You are an expert AI Travel Planner. Your task is to generate a comprehensive, curated "
        "day-by-day travel itinerary with realistic geo-coordinates, prices, time slots, and ratings.\n"
        "STRICT TOKEN EFFICIENCY & QUALITY RULES:\n"
        "1. OPTIMIZE FOR TOKEN COUNT: Keep outputs extremely concise and focused.\n"
        "2. DO NOT HALLUCINATE: Provide accurate geographic coordinates and realistic landmark details.\n"
        "3. CONCISE FIELD VALUES: Keep activity descriptions strictly under 25 words.\n"
        "4. EXACT JSON ONLY: Return strictly valid JSON adhering to the specified schema."
    )


def build_planner_user_prompt(
    prompt: str,
    origin_code: str,
    dest_clean: str,
    start_date: str,
    end_date: str,
    duration_days: int,
    passengers_count: int,
    rooms_calculated: int,
    cars_calculated: int,
    style: Optional[str],
    budget: Optional[str],
    include_flights: bool,
    include_hotels: bool,
    include_cars: bool,
    include_trains: bool,
    include_buses: bool,
    include_attractions: bool,
    include_activities: bool,
    include_seasonal_attractions: bool,
    include_seasonal_activities: bool,
    is_road_trip: bool,
    is_cruise: bool,
    is_fly_and_drive: bool,
    outbound_dep: str,
    outbound_arr: str,
    return_dep: str,
    return_arr: str,
) -> tuple[str, str]:
    """
    Constructs the detailed user prompt with modality-specific guidelines:
    Road Trips (highways/byways/scenic waypoints), Cruises (ports/sail-away), and Flights (live schedule).
    Returns (user_prompt, effective_style).
    """
    # Resolve Lunch and Temporal Boundary Rules
    is_late_arrival = False
    if outbound_arr and "PM" in str(outbound_arr).upper():
        try:
            hour_num = int(str(outbound_arr).split(":")[0].strip())
            if hour_num == 12 or (1 <= hour_num < 12):
                is_late_arrival = True
        except Exception:
            pass

    lunch_instruction = (
        PromptLoader.load_rule_prompt("airport_lunch", arrival_time=outbound_arr)
        if is_late_arrival
        else PromptLoader.load_rule_prompt("lunch_cutoff")
    )
    evening_breakfast_instruction = PromptLoader.load_rule_prompt("temporal_boundaries")

    # Resolve Modality Specific Guidelines
    if is_cruise:
        modality_text = PromptLoader.load_modality_prompt("cruise", origin=origin_code, destination=dest_clean, duration_minus_1=duration_days - 1)
        flight_schedule_text = ""
    elif is_road_trip or is_fly_and_drive:
        modality_text = PromptLoader.load_modality_prompt(
            "road_trip" if is_road_trip else "fly_and_drive",
            origin=origin_code,
            destination=dest_clean,
            duration=duration_days,
            duration_minus_1=duration_days - 1,
        )
        flight_schedule_text = f"DEPARTURE LOGISTICS: Pick up rental vehicle in {origin_code} at 08:30 AM - 09:00 AM. Morning road trip drive departs {origin_code} at 09:00 AM heading toward {dest_clean}.\n"
    elif include_flights:
        modality_text = PromptLoader.load_modality_prompt("flight_vacation", origin=origin_code, destination=dest_clean, duration=duration_days)
        flight_schedule_text = (
            f"EXACT LIVE FLIGHT SCHEDULE FROM AI SEARCH:\n"
            f"- Outbound Flight: Departs {origin_code} at {outbound_dep}, Arrives in {dest_clean} at {outbound_arr}.\n"
            f"- Return Flight: Departs {dest_clean} at {return_dep}, Arrives in {origin_code} at {return_arr}.\n"
            f"{lunch_instruction}\n"
        )
    else:
        modality_text = ""
        flight_schedule_text = f"DEPARTURE LOGISTICS: Depart from {origin_code} at 09:00 AM heading toward {dest_clean}.\n"

    # Resolve Thematic Style
    p_lower = prompt.lower()
    if any(w in p_lower for w in ["romantic", "honeymoon", "couples", "anniversary"]):
        effective_style = "romantic"
    elif any(w in p_lower for w in ["family", "kids", "children"]):
        effective_style = "family"
    elif any(w in p_lower for w in ["architecture", "architectural", "buildings", "monuments"]):
        effective_style = "architecture"
    elif any(w in p_lower for w in ["culinary", "food", "wine", "gastronomy", "dining", "foodie"]):
        effective_style = "culinary"
    elif any(w in p_lower for w in ["adventure", "hiking", "outdoor", "nature", "trails", "mountains", "beach", "surf", "ski"]):
        effective_style = "adventure"
    elif any(w in p_lower for w in ["budget", "cheap", "backpacking", "saver", "low cost"]):
        effective_style = "budget"
    elif any(w in p_lower for w in ["luxury", "vip", "michelin", "penthouse"]):
        effective_style = "luxury"
    elif any(w in p_lower for w in ["cultural", "history", "heritage", "museum"]):
        effective_style = "cultural"
    else:
        effective_style = (style or "balanced").strip().lower()

    thematic_prompt_text = PromptLoader.load_style_prompt(effective_style)

    # Resolve Timeline Requirement
    if is_cruise:
        timeline_text = f"TIMELINE REQUIREMENT: On Day 1, embark at departure port {origin_code}. On Days 2 through {duration_days - 1}, explore designated ports of call and shore excursions. On Day {duration_days}, arrive at final port and complete debarkation."
    elif include_flights:
        timeline_text = f"TIMELINE REQUIREMENT: On Day 1, schedule all activities strictly after flight arrival at {outbound_arr}. On Final Day, wrap up before flight departure at {return_dep}."
    else:
        timeline_text = f"TIMELINE REQUIREMENT (DEFAULT ROUND-TRIP): On Day 1, depart {origin_code} at 09:00 AM on the outbound corridor. On Final Day (Day {duration_days}), execute the return driving journey back to {origin_code}, arriving in {origin_code} by 05:30 PM for vehicle return, followed by dinner at 08:00 PM and rest in {origin_code}."

    # Resolve Vehicle Logistics Rule
    if include_cars:
        if is_road_trip or not include_flights:
            car_logistics_text = PromptLoader.load_rule_prompt("road_trip_car_logistics", origin=origin_code, duration=duration_days)
        else:
            car_logistics_text = PromptLoader.load_rule_prompt("flight_car_logistics", destination=dest_clean, duration=duration_days)
    else:
        car_logistics_text = "RENTAL VEHICLE LOGISTICS: No rental car requested."

    hotel_breakfast_instruction = PromptLoader.load_rule_prompt("hotel_breakfast_protocol", duration=duration_days)
    safety_instruction = PromptLoader.load_rule_prompt("safety_and_walkability_standards")
    no_gaps_instruction = PromptLoader.load_rule_prompt("no_gaps_timeline_protocol")
    shopping_instruction = PromptLoader.load_rule_prompt("evening_shopping_protocol")
    next_act_instruction = PromptLoader.load_rule_prompt("next_activity_node_protocol")

    user_prompt = (
        f"Plan a {duration_days}-day trip from {origin_code} to {dest_clean} from {start_date} to {end_date} for {passengers_count} passenger(s). "
        f"Modality: {'Cruise' if is_cruise else ('Road Trip' if is_road_trip else 'Flight Vacation')}, Style: {effective_style}, Budget: {budget}.\n"
        f"{flight_schedule_text}"
        f"{modality_text}\n"
        f"{safety_instruction}\n"
        f"{no_gaps_instruction}\n"
        f"{shopping_instruction}\n"
        f"{next_act_instruction}\n"
        f"{evening_breakfast_instruction}\n"
        f"{hotel_breakfast_instruction}\n"
        f"{thematic_prompt_text}\n"
        f"{timeline_text}\n"
        f"{car_logistics_text}\n"
        f"Included components: Flights={include_flights}, Hotels={include_hotels} ({rooms_calculated} rooms), Cars={include_cars} ({cars_calculated} car), Trains={include_trains}, Buses={include_buses}, "
        f"Attractions={include_attractions}, Activities={include_activities}, SeasonalAttractions={include_seasonal_attractions}, SeasonalActivities={include_seasonal_activities}. Prompt details: '{prompt}'.\n"
        f"OUTPUT FORMAT REQUIREMENT: Return strictly valid JSON with top-level 'days' array matching: {{\"days\": [{{\"day_number\": 1, \"date\": \"{start_date}\", \"theme\": \"...\", \"activities\": [..., {{\"name\": \"...\", \"time_slot\": \"08:00 AM - 09:00 AM\", \"category\": \"...\", \"description\": \"...\", \"travel_mode\": \"...\", \"next_activity\": {{\"name\": \"...\", \"distance_km\": 5.0, \"distance_miles\": 3.1, \"travel_time_minutes\": 15, \"travel_time_display\": \"15 mins\", \"travel_mode\": \"walk\", \"transit_summary\": \"...\"}}}}]}}]}}."
    )

    return user_prompt, effective_style

