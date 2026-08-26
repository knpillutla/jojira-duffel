"""
Places & Geolocation Management API Router.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ...services.locations import (
    CONFIG_FILE,
    GEO_LOCATIONS,
    resolve_geo_location,
    sync_locations_from_duffel,
)
from .common import get_duffel_client

router = APIRouter(prefix="/api/v1/places", tags=["Places & Geolocations"])


@router.post("/sync", summary="Sync Places & Cities from Duffel API into Config File")
def sync_places_endpoint(client: Any = Depends(get_duffel_client)) -> dict[str, Any]:
    """
    Calls Duffel Air/Places APIs to retrieve cities and airports with geolocations,
    saving the result into src/duffel/config/geo_locations.json for offline & runtime lookup.
    """
    try:
        res = sync_locations_from_duffel(client.adapter)
        return res
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed syncing locations from Duffel: {err}")


@router.get("/locations", summary="List All Loaded Geolocation Mappings")
def list_locations_endpoint() -> dict[str, Any]:
    """
    Returns all currently loaded location geolocations from the config file / memory cache.
    """
    return {
        "status": "success",
        "total_locations": len(GEO_LOCATIONS),
        "config_file": str(CONFIG_FILE),
        "locations": GEO_LOCATIONS,
    }


@router.get("/search", summary="Search / Resolve Location String to Geographic Coordinates")
def search_location_endpoint(q: str = Query(..., description="Location string e.g. 'Albany (ALB)', 'LAX', 'Paris'")) -> dict[str, Any]:
    """
    Resolves a location query string to latitude and longitude coordinates.
    """
    try:
        coords = resolve_geo_location(q)
        return {
            "status": "success",
            "query": q,
            "coordinates": coords,
        }
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err))
