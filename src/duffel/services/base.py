"""
Base service class for API operations.
"""

import json
import os
import re
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..http_client import HTTPClient


def save_output_file(
    filename: str,
    data: Any,
    subfolder: str = "",
    config: Optional[Any] = None,
    force: bool = False,
) -> Optional[str]:
    """
    Saves an output JSON payload into output/ if config.debug is True (or force is True).
    """
    if config is None:
        try:
            from ..config import DuffelConfig
            config = DuffelConfig()
        except Exception:
            config = None

    debug_enabled = getattr(config, "debug", False) if config else False
    if not debug_enabled and not force and subfolder != "llm":
        return None

    base_name = re.sub(r"[^\w\-. ]", "_", str(filename)).strip()
    if not base_name.endswith(".json"):
        base_name += ".json"

    saved_path = None
    root_dir = "output"
    try:
        target_dir = os.path.join(root_dir, subfolder) if subfolder else root_dir
        os.makedirs(target_dir, exist_ok=True)
        full_path = os.path.join(target_dir, base_name)
        with open(full_path, "w", encoding="utf-8") as f:
            if isinstance(data, (dict, list)):
                json.dump(data, f, indent=2, ensure_ascii=False)
            elif hasattr(data, "to_dict"):
                json.dump(data.to_dict(), f, indent=2, ensure_ascii=False)
            else:
                f.write(str(data))
        saved_path = full_path
    except Exception as e:
        print(f"[OUTPUT FILE NOTICE] Could not write '{base_name}' to '{root_dir}': {e}")

    if saved_path and debug_enabled:
        print(f"[DEBUG OUTPUT] Exported debug file: '{saved_path}'")
    return saved_path


class BaseService:
    """Base class for domain specific services."""

    def __init__(
        self,
        http_client: "HTTPClient",
        cache: Optional[Any] = None,
        adapter: Optional[Any] = None,
    ):
        self.client = http_client
        self.cache = cache
        if adapter is not None:
            self.adapter = adapter
        else:
            from ..adapters.duffel_adapter import DuffelProviderAdapter
            self.adapter = DuffelProviderAdapter(http_client=http_client)

    def save_debug_output(
        self,
        filename: str,
        data: Any,
        subfolder: str = "",
        force: bool = False,
    ) -> Optional[str]:
        """
        Saves output payload to output/ and outputs/ if debug is True in DuffelConfig.
        """
        cfg = getattr(self.client, "config", None)
        if not cfg:
            cfg = getattr(self, "config", None)
        return save_output_file(
            filename=filename,
            data=data,
            subfolder=subfolder,
            config=cfg,
            force=force,
        )
