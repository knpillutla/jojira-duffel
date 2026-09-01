"""
Backward-compatibility bridge for Planner prompt building.
Redirects to the centralized duffel.prompts module.
"""

from ...prompts import PromptLoader, build_planner_system_prompt, build_planner_user_prompt

__all__ = [
    "PromptLoader",
    "build_planner_system_prompt",
    "build_planner_user_prompt",
]
