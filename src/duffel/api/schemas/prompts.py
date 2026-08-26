"""
Popular & Trending Search Prompts Pydantic schemas for Duffel REST API.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class PopularPromptItem(BaseModel):
    """Popular search prompt item with UI title, full prompt text, and pre-parsed form parameters."""
    id: str = Field(..., description="Unique prompt ID e.g. 'p_fl_001'")
    title: str = Field(..., description="Catchy short title string for UI button/card rendering")
    prompt: str = Field(..., description="Full natural language prompt text")
    category: str = Field(..., description="Category: flights, cars, hotels, bundles, ai_trip_planner, ai_search")
    badge: Optional[str] = Field(None, description="Optional UI badge tag e.g. '🔥 Top Trending', '5% Savings'")
    trending_score: int = Field(90, ge=1, le=100, description="Trending popularity score out of 100")
    search_params: dict[str, Any] = Field(..., description="Pre-parsed search parameter dict to populate search panel form fields")


class PopularPromptsResponse(BaseModel):
    """Popular prompts API response."""
    status: str = Field("success", description="Status of API response")
    categories: dict[str, list[PopularPromptItem]] = Field(..., description="Map of category names to lists of popular prompts")
    total_prompts: int = Field(..., description="Total count of prompts returned across requested categories")
