"""
Modular Prompt Loader for Provider-Model Template Management.
Loads prompts from dedicated provider-model JSON files (e.g. prompts/openai-gpt-4o.json)
with fallback hierarchy to provider level, default file, and system_prompts.json.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional


class PromptLoader:
    """Thread-safe prompt loader with in-memory caching."""

    _CACHE: dict[str, dict[str, Any]] = {}
    _PROMPTS_DIR: Optional[Path] = None

    @classmethod
    def get_prompts_dir(cls) -> Path:
        if cls._PROMPTS_DIR is None:
            # Check current workspace root or relative paths
            candidates = [
                Path("prompts"),
                Path(__file__).resolve().parent.parent.parent.parent / "prompts",
            ]
            for c in candidates:
                if c.is_dir():
                    cls._PROMPTS_DIR = c
                    break
            if cls._PROMPTS_DIR is None:
                cls._PROMPTS_DIR = Path("prompts")
        return cls._PROMPTS_DIR

    @classmethod
    def _read_json(cls, file_path: Path) -> dict[str, Any]:
        p_str = str(file_path.resolve())
        if p_str in cls._CACHE:
            return cls._CACHE[p_str]
        try:
            if file_path.is_file():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cls._CACHE[p_str] = data
                    return data
        except Exception as err:
            print(f"[PROMPT LOADER] Notice reading {file_path}: {err}")
        return {}

    @classmethod
    def load_prompt(
        cls,
        prompt_key: str,
        provider: str = "openai",
        model: str = "gpt-4o",
        config: Optional[Any] = None,
    ) -> str:
        """
        Loads prompt string following resolution hierarchy:
        1. prompts/{provider}-{model}.json
        2. prompts/{provider}.json
        3. prompts/default.json
        4. config.system_prompts or system_prompts.json
        """
        prov_clean = (provider or "openai").lower().strip()
        model_clean = (model or "").lower().strip().replace("/", "-")
        prompts_dir = cls.get_prompts_dir()

        # 1. Try prompts/{provider}-{model}.json
        if model_clean:
            specific_file = prompts_dir / f"{prov_clean}-{model_clean}.json"
            data = cls._read_json(specific_file)
            if data and prompt_key in data:
                return data[prompt_key]

        # 2. Try prompts/{provider}.json
        prov_file = prompts_dir / f"{prov_clean}.json"
        data = cls._read_json(prov_file)
        if data and prompt_key in data:
            return data[prompt_key]

        # 3. Try prompts/default.json
        default_file = prompts_dir / "default.json"
        data = cls._read_json(default_file)
        if data and prompt_key in data:
            return data[prompt_key]

        # 4. Try config.system_prompts
        if config:
            sp_map = getattr(config, "system_prompts", {}) or {}
            if model_clean and f"{prompt_key}_{prov_clean}_{model_clean}" in sp_map:
                return sp_map[f"{prompt_key}_{prov_clean}_{model_clean}"]
            if f"{prompt_key}_{prov_clean}" in sp_map:
                return sp_map[f"{prompt_key}_{prov_clean}"]
            if prompt_key in sp_map:
                return sp_map[prompt_key]

        return ""

    @classmethod
    def load_style_prompt(cls, style: str) -> str:
        """Loads style-specific prompt snippet from prompts/styles.json."""
        s_clean = (style or "balanced").lower().strip()
        data = cls._read_json(cls.get_prompts_dir() / "styles.json")
        return data.get(s_clean) or data.get("balanced", "")

    @classmethod
    def load_modality_prompt(cls, modality: str, **kwargs) -> str:
        """Loads travel modality prompt snippet (road_trip, flight_vacation, cruise, fly_and_drive) from prompts/modalities.json."""
        m_clean = (modality or "flight_vacation").lower().strip()
        data = cls._read_json(cls.get_prompts_dir() / "modalities.json")
        raw_tmpl = data.get(m_clean, "")
        if raw_tmpl and kwargs:
            try:
                return raw_tmpl.format(**kwargs)
            except Exception:
                pass
        return raw_tmpl

    @classmethod
    def load_rule_prompt(cls, rule_key: str, **kwargs) -> str:
        """Loads operating rule snippet from prompts/rules.json."""
        data = cls._read_json(cls.get_prompts_dir() / "rules.json")
        raw_tmpl = data.get(rule_key, "")
        if raw_tmpl and kwargs:
            try:
                return raw_tmpl.format(**kwargs)
            except Exception:
                pass
        return raw_tmpl
