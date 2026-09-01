from datetime import datetime, timezone
import json
import time
from typing import Any, Optional

# Global In-Memory LLM Metrics Tracking Counter
_LLM_METRICS_COUNTER: dict[str, Any] = {
    "total_llm_calls": 0,
    "openai_calls": 0,
    "gemini_calls": 0,
    "template_fallback_calls": 0,
    "last_call_timestamp": None,
}


def save_llm_debug_output(category: str, data: dict[str, Any], identifier: str = ""):
    """Saves LLM extraction, generated itinerary, and final response payloads into output/llm/."""
    if "extraction" in category or "input" in category:
        filename = "llm_input_extraction.json"
    elif "final" in category or "response" in category:
        filename = "llm_final_response.json"
    else:
        filename = "llm_itinerary.json"
    from ..base import save_output_file
    save_output_file(filename=filename, data=data, subfolder="llm", force=True)


def extract_days_from_llm_payload(payload: Any) -> Optional[list[dict[str, Any]]]:
    """Recursively locates and returns the list of daily itinerary dicts from any LLM JSON response structure."""
    if isinstance(payload, list):
        if payload and isinstance(payload[0], dict):
            return payload
        return None

    if not isinstance(payload, dict):
        return None

    for key in ["days", "daily_itinerary", "itinerary", "itinerary_days", "schedule", "trip_days", "plan"]:
        val = payload.get(key)
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return val
        elif isinstance(val, dict):
            sub_res = extract_days_from_llm_payload(val)
            if sub_res:
                return sub_res

    for k, v in payload.items():
        if isinstance(v, dict):
            sub_res = extract_days_from_llm_payload(v)
            if sub_res:
                return sub_res
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            first_elem = v[0]
            if any(prop in first_elem for prop in ["day_number", "day", "date", "theme", "title", "activities", "items", "events", "schedule", "attractions"]):
                return v

    return None


def orchestrate_llm_itinerary(
    config: Any,
    system_prompt: str,
    user_prompt: str,
    destination: str,
    duration_days: int,
    start_dt: datetime,
    base_lat: float,
    base_lng: float,
    include_attractions: bool,
    include_activities: bool,
    include_cars: bool = True,
    origin: Optional[str] = None,
    is_road_trip: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Orchestrates LLM call to OpenAI/Gemini prioritizing the configured llm_planner_provider.
    Returns tuple of (days_list, llm_meta).
    """
    cfg = config
    is_test_mode = bool(getattr(cfg, "test_mode", False)) if cfg else False
    openai_key = getattr(cfg, "openai_api_key", "") if cfg else ""
    gemini_key = getattr(cfg, "gemini_api_key", "") if cfg else ""
    planner_provider = (
        getattr(cfg, "llm_planner_provider", "")
        or getattr(cfg, "llm_travel_provider", "")
        or getattr(cfg, "llm_provider", "openai")
        or "openai"
    ).lower()
    llm_errors: list[str] = []

    def _try_openai() -> Optional[tuple[list[dict[str, Any]], dict[str, Any]]]:
        if not (openai_key and getattr(cfg, "openai_enabled", True)):
            return None
        from .prompts import build_planner_system_prompt
        model_name = getattr(cfg, "openai_planner_model", "") or getattr(cfg, "openai_travel_model", "") or getattr(cfg, "openai_model", "gpt-4o") or "gpt-4o"
        active_sys_prompt = build_planner_system_prompt(cfg, provider="openai", model=model_name) or system_prompt
        llm_timeout = float(getattr(cfg, "timeout", 120.0))
        t0_llm = 0.0
        try:
            t0_llm = time.perf_counter()
            raw_text = None
            try:
                import openai
                o_client = openai.OpenAI(api_key=openai_key, timeout=llm_timeout)
                resp = o_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": active_sys_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7,
                )
                raw_text = resp.choices[0].message.content
            except (ImportError, ModuleNotFoundError):
                from urllib.request import Request, urlopen
                from urllib.error import HTTPError
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": active_sys_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.7,
                }
                req_obj = Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {openai_key}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                try:
                    with urlopen(req_obj, timeout=llm_timeout) as resp_http:
                        http_data = json.loads(resp_http.read().decode("utf-8"))
                        raw_text = http_data["choices"][0]["message"]["content"]
                except HTTPError as http_err:
                    err_body = http_err.read().decode("utf-8", errors="ignore")
                    raise RuntimeError(f"OpenAI API HTTP {http_err.code}: {err_body}")

            if raw_text:
                parsed = json.loads(raw_text)
                days_out = extract_days_from_llm_payload(parsed)
                if days_out:
                    llm_dur_ms = (time.perf_counter() - t0_llm) * 1000.0
                    try:
                        from ...timing import TimingTracker
                        TimingTracker.add_llm_time(llm_dur_ms)
                    except Exception:
                        pass
                    _LLM_METRICS_COUNTER["total_llm_calls"] += 1
                    _LLM_METRICS_COUNTER["openai_calls"] += 1
                    _LLM_METRICS_COUNTER["last_call_timestamp"] = datetime.now(timezone.utc).isoformat()
                    print(f"[PLANNER LLM SUCCESS] Live OpenAI '{model_name}' generated {len(days_out)} day itinerary ({llm_dur_ms:.1f}ms).")
                    save_llm_debug_output(
                        category="llm_itinerary_openai",
                        data={
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "destination": destination,
                            "duration_days": duration_days,
                            "user_prompt": user_prompt,
                            "system_prompt": system_prompt,
                            "llm_metadata": {"is_live_llm": True, "llm_provider": "openai", "llm_model": model_name},
                            "itinerary_days": days_out
                        },
                        identifier=destination
                    )
                    return days_out, {"is_live_llm": True, "llm_provider": "openai", "llm_model": model_name}
                else:
                    raise ValueError(f"OpenAI returned JSON without valid days array: {raw_text[:200]}")
        except Exception as llm_err:
            if t0_llm > 0:
                llm_dur_ms = (time.perf_counter() - t0_llm) * 1000.0
                try:
                    from ...timing import TimingTracker
                    TimingTracker.add_llm_time(llm_dur_ms)
                except Exception:
                    pass
            llm_errors.append(f"OpenAI ({model_name}) error: {llm_err}")
            print(f"[PLANNER LLM NOTICE] OpenAI execution notice: {llm_err}.")
            return None

    def _try_gemini() -> Optional[tuple[list[dict[str, Any]], dict[str, Any]]]:
        if not (gemini_key and getattr(cfg, "gemini_enabled", True)):
            return None
        from .prompts import build_planner_system_prompt
        gemini_model = getattr(cfg, "gemini_planner_model", "") or getattr(cfg, "gemini_travel_model", "") or getattr(cfg, "gemini_model", "gemini-1.5-pro") or "gemini-1.5-pro"
        active_sys_prompt = build_planner_system_prompt(cfg, provider="gemini", model=gemini_model) or system_prompt
        llm_timeout = float(getattr(cfg, "timeout", 120.0))
        t0_llm = 0.0
        try:
            t0_llm = time.perf_counter()
            import httpx
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={gemini_key}"
            resp = httpx.post(url, json={
                "contents": [{"parts": [{"text": f"{active_sys_prompt}\n\nUser Request: {user_prompt}\nRespond with strictly valid JSON matching {{\"days\": [...]}}"}]}],
                "generationConfig": {"response_mime_type": "application/json"}
            }, timeout=llm_timeout)
            if resp.is_success:
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_text)
                days_out = extract_days_from_llm_payload(parsed)
                if days_out:
                    llm_dur_ms = (time.perf_counter() - t0_llm) * 1000.0
                    try:
                        from ...timing import TimingTracker
                        TimingTracker.add_llm_time(llm_dur_ms)
                    except Exception:
                        pass
                    _LLM_METRICS_COUNTER["total_llm_calls"] += 1
                    _LLM_METRICS_COUNTER["gemini_calls"] += 1
                    _LLM_METRICS_COUNTER["last_call_timestamp"] = datetime.now(timezone.utc).isoformat()
                    print(f"[PLANNER LLM SUCCESS] Live Gemini '{gemini_model}' generated {len(days_out)} day itinerary ({llm_dur_ms:.1f}ms).")
                    save_llm_debug_output(
                        category="llm_itinerary_gemini",
                        data={
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "destination": destination,
                            "duration_days": duration_days,
                            "user_prompt": user_prompt,
                            "system_prompt": system_prompt,
                            "llm_metadata": {"is_live_llm": True, "llm_provider": "gemini", "llm_model": gemini_model},
                            "itinerary_days": days_out
                        },
                        identifier=destination
                    )
                    return days_out, {"is_live_llm": True, "llm_provider": "gemini", "llm_model": gemini_model}
                else:
                    raise ValueError(f"Gemini returned JSON without valid days array: {raw_text[:200]}")
            else:
                raise RuntimeError(f"Gemini API returned HTTP {resp.status_code}: {resp.text}")
        except Exception as gem_err:
            if t0_llm > 0:
                llm_dur_ms = (time.perf_counter() - t0_llm) * 1000.0
                try:
                    from ...timing import TimingTracker
                    TimingTracker.add_llm_time(llm_dur_ms)
                except Exception:
                    pass
            llm_errors.append(f"Gemini ({gemini_model}) error: {gem_err}")
            print(f"[PLANNER LLM NOTICE] Gemini execution notice: {gem_err}.")
            return None

    if planner_provider == "gemini":
        gem_res = _try_gemini()
        if gem_res is not None:
            return gem_res
        open_res = _try_openai()
        if open_res is not None:
            return open_res
    else:
        open_res = _try_openai()
        if open_res is not None:
            return open_res
        gem_res = _try_gemini()
        if gem_res is not None:
            return gem_res

    if not is_test_mode:
        err_details = " | ".join(llm_errors) if llm_errors else f"LLM keys missing or provider '{planner_provider}' failed"
        raise RuntimeError(
            f"Itinerary generation failed: Live LLM ({planner_provider}) could not generate itinerary ({err_details}). "
            f"Synthetic fallback is strictly disabled in production mode."
        )

    _LLM_METRICS_COUNTER["total_llm_calls"] += 1
    _LLM_METRICS_COUNTER["template_fallback_calls"] += 1
    return [], {"is_live_llm": False, "llm_provider": "template_fallback", "llm_model": "deterministic_synthesizer"}
