"""Curated Gemini model catalog for UI selection."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Safe fallback when Google list_models is unavailable.
DEFAULT_GEMINI_MODELS: List[Dict[str, str]] = [
    {
        "id": "gemini-2.5-flash",
        "display_name": "Gemini 2.5 Flash",
        "description": "Fast, cost-efficient default",
    },
    {
        "id": "gemini-2.5-pro",
        "display_name": "Gemini 2.5 Pro",
        "description": "Higher quality for complex tasks",
    },
    {
        "id": "gemini-2.0-flash",
        "display_name": "Gemini 2.0 Flash",
        "description": "Previous flash generation",
    },
]


def default_agent_model() -> str:
    """Return the process default model from env."""
    return os.getenv("AGENT_MODEL", "gemini-2.5-flash")


def curated_model_ids() -> Set[str]:
    """Return the set of models the UI may select."""
    ids = {m["id"] for m in DEFAULT_GEMINI_MODELS}
    ids.add(default_agent_model())
    return ids


def is_allowed_model(model_name: str) -> bool:
    """Whether a model name may be assigned to a chat."""
    if not model_name or not isinstance(model_name, str):
        return False
    name = model_name.strip()
    if not name:
        return False
    # Allow curated list; also accept other gemini-* ids so env overrides work.
    if name in curated_model_ids():
        return True
    return name.startswith("gemini-")


def list_available_models() -> List[Dict[str, Any]]:
    """List models for the UI, preferring live Google catalog with fallback."""
    default = default_agent_model()
    by_id: Dict[str, Dict[str, Any]] = {
        m["id"]: {**m, "is_default": m["id"] == default} for m in DEFAULT_GEMINI_MODELS
    }

    if default not in by_id:
        by_id[default] = {
            "id": default,
            "display_name": default,
            "description": "Configured AGENT_MODEL",
            "is_default": True,
        }

    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key and api_key != "your_api_key_here":
        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            for model in genai.list_models():
                methods = getattr(model, "supported_generation_methods", None) or []
                if "generateContent" not in methods:
                    continue
                raw_name = getattr(model, "name", "") or ""
                model_id = raw_name.replace("models/", "")
                if not model_id.startswith("gemini-"):
                    continue
                if model_id not in by_id:
                    by_id[model_id] = {
                        "id": model_id,
                        "display_name": getattr(model, "display_name", None) or model_id,
                        "description": getattr(model, "description", None) or "",
                        "is_default": model_id == default,
                    }
        except Exception as exc:
            logger.warning("Falling back to curated model list: %s", exc)

    # Prefer curated order first, then any extras alphabetically.
    curated_order = [m["id"] for m in DEFAULT_GEMINI_MODELS]
    ordered: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for mid in curated_order:
        if mid in by_id:
            ordered.append(by_id[mid])
            seen.add(mid)
    for mid in sorted(by_id.keys()):
        if mid not in seen:
            ordered.append(by_id[mid])
    return ordered


def resolve_chat_model(chat_model: Optional[str]) -> str:
    """Resolve effective model: chat override → env → default."""
    if chat_model and isinstance(chat_model, str) and chat_model.strip():
        return chat_model.strip()
    return default_agent_model()
