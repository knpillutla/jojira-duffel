from typing import Any, Optional


def build_planner_system_prompt(config: Any) -> str:
    """Loads base system prompt and formats timing, safety, and modality instructions."""
    sp_map = getattr(config, "system_prompts", {}) if config else {}
    return sp_map.get("planner_system_prompt") or (
        "You are an expert AI Travel Planner. Your task is to generate a comprehensive, curated "
        "day-by-day travel itinerary with realistic geo-coordinates, prices, time slots, and ratings.\n"
        "STRICT TOKEN EFFICIENCY & QUALITY RULES:\n"
        "1. OPTIMIZE FOR TOKEN COUNT: Keep outputs extremely concise and focused. Do NOT provide conversational filler, redundant text, or additional explanations unless specifically requested.\n"
        "2. DO NOT HALLUCINATE: Provide accurate geographic coordinates, realistic location names, and factual landmark details.\n"
        "3. CONCISE FIELD VALUES: Keep activity descriptions strictly under 25 words (1-2 short sentences maximum).\n"
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
    # Check if flight arrival is after 12:00 PM to mandate Airport Terminal Lunch
    is_late_arrival = False
    if outbound_arr and "PM" in str(outbound_arr).upper():
        try:
            hour_num = int(str(outbound_arr).split(":")[0].strip())
            if hour_num == 12 or (1 <= hour_num < 12):
                is_late_arrival = True
        except Exception:
            pass

    lunch_instruction = (
        f"AIRPORT LUNCH PROTOCOL (FLIGHT ARRIVAL AT {outbound_arr}): Outbound flight arrives at {outbound_arr} (after 12:00 PM). "
        f"Schedule Day 1 Lunch IMMEDIATELY at an Airport Terminal Restaurant/Cafe upon landing (e.g. at 01:00 PM) before picking up rental car or traveling into the city center, "
        f"otherwise it will be too late to pick up the rental car or eat. LUNCH MUST NEVER BE SCHEDULED AFTER 02:00 PM ON ANY DAY!"
    ) if is_late_arrival else "LUNCH CUTOFF RULE: Lunch every day MUST NEVER be scheduled after 02:00 PM (schedule between 11:30 AM and 01:30 PM)."

    evening_breakfast_instruction = (
        "DAILY OPERATING BOUNDARIES & TIMELINE RULES (STRICTLY ENFORCED):\n"
        "- DAY START AT 08:00 AM: Every full day MUST start at 08:00 AM at best (with Breakfast or Quick Grab-and-Go Coffee Shop). Never start activities before 08:00 AM.\n"
        "- ATTRACTION END CUTOFF (08:00 PM MAXIMUM): Any attraction, museum, or sightseeing activity MUST end by 08:00 PM at the latest (e.g. 05:45 PM - 07:45 PM). NEVER extend any attraction past 08:00 PM (NEVER 08:30 PM, 09:00 PM, or 10:45 PM).\n"
        "- MANDATORY DINNER START AT 08:00 PM: Dinner MUST start at 08:00 PM at any cost (e.g. 08:00 PM - 09:30 PM). Never start dinner after 08:00 PM.\n"
        "- MANDATORY HOTEL RETURN BEFORE 10:00 PM: The final step of EVERY day MUST be 'Return to Hotel & Rest for the Night', with hotel arrival strictly BEFORE 10:00 PM (scheduled between 09:30 PM and 10:00 PM).\n"
        "- NO OVERNIGHT / EARLY MORNING SLOTS: Under no circumstances should any activity, dinner, or hotel return be scheduled past 10:00 PM (never 10:30 PM, 11:00 PM, 12:00 AM, 01:00 AM, or 06:15 AM).\n"
        "- MORNING BREAKFAST PROTOCOL: Every next day MUST begin with Breakfast at 08:00 AM. If sit-in breakfast is not possible due to morning time constraints or tight schedules, recommend a nearby local coffee shop, artisanal bakery, or quick cafe to grab coffee & pastries instead of a long sit-in breakfast."
    )

    road_trip_corridor_text = (
        f"ROAD TRIP HIGHWAY CORRIDOR REQUIREMENT:\n"
        f"This is a driving Road Trip from {origin_code} to {dest_clean}. "
        f"Do NOT restrict activities solely to {dest_clean}. Construct the itinerary along the authentic driving highway and scenic byway corridor "
        f"featuring famous en-route waypoints, roadside diners, national/state parks, scenic lookouts, and intermediate overnight stays "
        f"progressing day-by-day from {origin_code} to {dest_clean} and back. Set 'travel_mode': 'drive' for all driving legs. "
        f"Road trip package bundles are categorized as: 'shortest' (Direct Highway / Express corridor), 'scenic' (Scenic Byways, Panoramas, Nature trails), and 'longest' (Extended Regional Explorer, Historic Towns).\n"
    ) if (is_road_trip or is_fly_and_drive) else ""

    cruise_instruction_text = (
        f"CRUISE & MARITIME VOYAGE LOGISTICS:\n"
        f"This is an Ocean/River Cruise departing from {origin_code} to {dest_clean}. "
        f"Day 1: Port embarkation, ship check-in, and scenic sail-away viewing. "
        f"Days 2 to {duration_days - 1}: Daily ports-of-call, shore excursions, coastal promenade walks, harbor dining, and maritime activities with 'travel_mode': 'boat' or 'ferry'. "
        f"Final Day: Return port debarkation and departure.\n"
    ) if is_cruise else ""

    flight_schedule_text = (
        f"EXACT LIVE FLIGHT SCHEDULE FROM AI SEARCH:\n"
        f"- Outbound Flight: Departs {origin_code} at {outbound_dep}, Arrives in {dest_clean} at {outbound_arr}.\n"
        f"- Return Flight: Departs {dest_clean} at {return_dep}, Arrives in {origin_code} at {return_arr}.\n"
        f"{lunch_instruction}\n"
        f"Flight package bundles are categorized as: 'cheapest' (Budget Saver), 'moderate' (Balanced Choice), and 'luxury' (Signature Luxury VIP).\n"
    ) if include_flights else (
        f"DEPARTURE LOGISTICS: Road trip drive departs from {origin_code} at 08:30 AM heading toward {dest_clean}.\n" if not is_cruise else ""
    )

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

    theme_instructions = {
        "romantic": "THEMATIC EMPHASIS (ROMANTIC & COUPLES ESCAPE): Focus on intimate scenic vistas, sunset viewpoints, candlelight dining, charming boutique neighborhoods, and couple-oriented activities.",
        "architecture": "THEMATIC EMPHASIS (ARCHITECTURE & DESIGN): Focus on iconic historic & modern architectural landmarks, guided building tours, famous bridges, cathedral domes, and design heritage.",
        "culinary": "THEMATIC EMPHASIS (CULINARY & GASTRONOMY): Focus on artisan food markets, traditional bistros, wine/sommelier cellars, chef's tastings, and regional culinary specialties.",
        "family": "THEMATIC EMPHASIS (FAMILY & ALL AGES): Focus on interactive museums, sprawling parks, kid-friendly walking routes, zoo/aquarium visits, and family dining.",
        "adventure": "THEMATIC EMPHASIS (OUTDOOR & ADVENTURE): Focus on nature trails, panoramic lookouts, bike rentals, waterfront activities, and active outdoor exploration.",
        "budget": "THEMATIC EMPHASIS (BUDGET & SMART EXPLORER): Focus on free/low-cost landmark visits, public gardens, scenic walking routes, and affordable local street food.",
        "luxury": "THEMATIC EMPHASIS (VIP & SIGNATURE LUXURY): Focus on private VIP access, Michelin-starred dining, private chauffeured tours, and luxury experiences.",
        "cultural": "THEMATIC EMPHASIS (CULTURE & HERITAGE): Focus on historic districts, UNESCO world heritage sites, renowned art museums, and authentic cultural landmarks.",
    }
    thematic_prompt_text = theme_instructions.get(effective_style, "")

    if is_cruise:
        timeline_text = f"TIMELINE REQUIREMENT: On Day 1, embark at departure port {origin_code}. On Days 2 through {duration_days - 1}, explore designated ports of call and shore excursions. On Day {duration_days}, arrive at final port and complete debarkation."
    elif include_flights:
        timeline_text = f"TIMELINE REQUIREMENT: On Day 1, schedule all activities strictly after flight arrival at {outbound_arr}. On Final Day, wrap up before flight departure at {return_dep}."
    else:
        timeline_text = f"TIMELINE REQUIREMENT: On Day 1, depart from origin at 08:30 AM and embark on the road trip corridor. On Final Day, return to origin by 06:00 PM."

    user_prompt = (
        f"Plan a {duration_days}-day trip from {origin_code} to {dest_clean} from {start_date} to {end_date} for {passengers_count} passenger(s). "
        f"Modality: {'Cruise' if is_cruise else ('Road Trip' if is_road_trip else 'Flight Vacation')}, Style: {effective_style}, Budget: {budget}.\n"
        f"{flight_schedule_text}"
        f"{road_trip_corridor_text}"
        f"{cruise_instruction_text}"
        f"{evening_breakfast_instruction}\n"
        f"{thematic_prompt_text}\n"
        f"{timeline_text}\n"
        f"RENTAL VEHICLE LOGISTICS: {'On Day 1 include rental car pickup upon departure/arrival, and on Day ' + str(duration_days) + ' include rental vehicle return & drop-off.' if include_cars else 'No rental car requested.'}\n"
        f"Included components: Flights={include_flights}, Hotels={include_hotels} ({rooms_calculated} rooms), Cars={include_cars} ({cars_calculated} car), Trains={include_trains}, Buses={include_buses}, "
        f"Attractions={include_attractions}, Activities={include_activities}, SeasonalAttractions={include_seasonal_attractions}, SeasonalActivities={include_seasonal_activities}. Prompt details: '{prompt}'.\n"
        f"OUTPUT FORMAT REQUIREMENT: Return strictly valid JSON with top-level 'days' array matching: {{\"days\": [{{\"day_number\": 1, \"date\": \"{start_date}\", \"theme\": \"...\", \"activities\": [...]}}]}}."
    )

    return user_prompt, effective_style
